from __future__ import annotations

import asyncio
import re
import secrets
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from pypdf import PdfReader


NUMBER_PATTERN = re.compile(r"\b([1-9]|[1-5][0-9]|60)\b")


@dataclass
class DrawAnalysis:
    hot_numbers: list[int]
    cold_numbers: list[int]
    parity_distribution: dict[str, float]
    repeated_numbers: list[int]
    rag_context: str


class HistoricalAnalystAgent:
    """Analisa os PDFs e produz sinais de tendência com RAG híbrido (léxico + frequência)."""

    def __init__(self, pdf_folder: str = "doc_pdf") -> None:
        self.pdf_folder = Path(pdf_folder)
        self._docs_cache: list[str] | None = None
        self._draws_cache: list[list[int]] | None = None

    def _load_pdf_texts(self) -> list[str]:
        if self._docs_cache is not None:
            return self._docs_cache

        texts: list[str] = []
        if self.pdf_folder.exists():
            for pdf_path in sorted(self.pdf_folder.glob("*.pdf")):
                reader = PdfReader(str(pdf_path))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                if text.strip():
                    texts.append(text)

        self._docs_cache = texts
        return texts

    def _extract_draws(self, texts: list[str]) -> list[list[int]]:
        if self._draws_cache is not None:
            return self._draws_cache

        draws: list[list[int]] = []
        for text in texts:
            numbers = [int(n) for n in NUMBER_PATTERN.findall(text)]
            for i in range(0, len(numbers), 6):
                block = numbers[i : i + 6]
                if len(block) == 6 and len(set(block)) == 6:
                    draws.append(sorted(block))

        self._draws_cache = draws
        return draws

    def _hybrid_rag_context(self, user_query: str, docs: list[str]) -> str:
        if not docs:
            return "Sem PDFs carregados na pasta doc_pdf."

        tokens = {t for t in re.findall(r"[a-zA-Zà-úÀ-Ú0-9]+", user_query.lower()) if len(t) > 2}
        scored_chunks: list[tuple[int, str]] = []

        for doc in docs:
            chunks = [doc[i : i + 1500] for i in range(0, len(doc), 1500)]
            for chunk in chunks:
                chunk_lower = chunk.lower()
                lexical_score = sum(1 for token in tokens if token in chunk_lower)
                frequency_signal = len(NUMBER_PATTERN.findall(chunk)) // 10
                score = lexical_score * 3 + frequency_signal
                if score > 0:
                    scored_chunks.append((score, chunk.strip()))

        best_chunks = [chunk for _, chunk in sorted(scored_chunks, key=lambda x: x[0], reverse=True)[:3]]
        return "\n\n".join(best_chunks) if best_chunks else "Nenhum trecho relevante encontrado nos PDFs."

    async def analyze(self, user_query: str) -> DrawAnalysis:
        docs = await asyncio.to_thread(self._load_pdf_texts)
        draws = await asyncio.to_thread(self._extract_draws, docs)
        rag_context = await asyncio.to_thread(self._hybrid_rag_context, user_query, docs)

        if not draws:
            default_numbers = list(range(1, 7))
            return DrawAnalysis(
                hot_numbers=default_numbers,
                cold_numbers=list(range(55, 61)),
                parity_distribution={"pares": 50.0, "ímpares": 50.0},
                repeated_numbers=[],
                rag_context=rag_context,
            )

        counter = Counter(n for draw in draws for n in draw)
        hot_numbers = [n for n, _ in counter.most_common(12)]

        all_numbers = set(range(1, 61))
        seen_numbers = set(counter)
        unseen = sorted(all_numbers - seen_numbers)
        cold_base = unseen[:12]
        if len(cold_base) < 12:
            least_common = sorted(counter.items(), key=lambda x: x[1])
            cold_base.extend([n for n, _ in least_common[: 12 - len(cold_base)]])

        total_numbers = sum(counter.values())
        even_count = sum(v for n, v in counter.items() if n % 2 == 0)
        odd_count = total_numbers - even_count

        repetition_counter: defaultdict[int, int] = defaultdict(int)
        for i in range(1, len(draws)):
            for n in set(draws[i - 1]).intersection(draws[i]):
                repetition_counter[n] += 1

        repeated_numbers = [n for n, _ in sorted(repetition_counter.items(), key=lambda x: x[1], reverse=True)[:8]]

        return DrawAnalysis(
            hot_numbers=hot_numbers,
            cold_numbers=cold_base,
            parity_distribution={
                "pares": round((even_count / total_numbers) * 100, 2),
                "ímpares": round((odd_count / total_numbers) * 100, 2),
            },
            repeated_numbers=repeated_numbers,
            rag_context=rag_context,
        )


class StatisticalAgent:
    """Valida combinações via probabilidade/combinatória e distribuição por quadrantes."""

    @staticmethod
    def _quadrant(number: int) -> int:
        if number <= 15:
            return 1
        if number <= 30:
            return 2
        if number <= 45:
            return 3
        return 4

    def validate(self, game: list[int]) -> dict[str, Any]:
        ordered = sorted(game)
        direct_sequence_penalty = 1.0 if ordered == list(range(ordered[0], ordered[0] + 6)) else 0.0

        diffs = [ordered[i + 1] - ordered[i] for i in range(5)]
        variance_signal = pstdev(diffs) if len(diffs) > 1 else 0.0
        number_std = pstdev(ordered)
        parity = {"pares": sum(1 for n in ordered if n % 2 == 0), "ímpares": sum(1 for n in ordered if n % 2 != 0)}

        quadrants = Counter(self._quadrant(n) for n in ordered)
        quadrant_values = [quadrants.get(i, 0) for i in range(1, 5)]
        quadrant_std = pstdev(quadrant_values)

        score = 100.0
        score -= direct_sequence_penalty * 35.0
        score -= max(0.0, 2.8 - variance_signal) * 4.0
        score -= abs(parity["pares"] - 3) * 6.0
        score -= quadrant_std * 8.0
        score = round(max(0.0, min(100.0, score)), 2)

        return {
            "jogo": ordered,
            "score_estatistico": score,
            "desvio_padrao_numeros": round(number_std, 4),
            "desvio_padrao_quadrantes": round(quadrant_std, 4),
            "pares_impares": parity,
            "quadrantes": {f"Q{i}": quadrants.get(i, 0) for i in range(1, 5)},
            "sequencia_direta": bool(direct_sequence_penalty),
        }


class RandomIntuitionAgent:
    """Gera entropia para evitar overfitting histórico."""

    def __init__(self) -> None:
        self._rng = secrets.SystemRandom()

    def generate(self, amount: int) -> list[list[int]]:
        games: list[list[int]] = []
        for _ in range(amount):
            game = sorted(self._rng.sample(range(1, 61), 6))
            games.append(game)
        return games


class ConversationMemory:
    """Memória conversacional simples por sessão."""

    def __init__(self) -> None:
        self._messages: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, role: str, content: str) -> None:
        async with self._lock:
            self._messages[session_id].append({"role": role, "content": content})

    async def history(self, session_id: str, limit: int = 10) -> list[dict[str, str]]:
        async with self._lock:
            return self._messages[session_id][-limit:]


class LeaderCoordinatorAgent:
    """Orquestra os especialistas e consolida os jogos finais."""

    def __init__(self, model_id: str = "gpt-4.1") -> None:
        self.historical = HistoricalAnalystAgent()
        self.statistical = StatisticalAgent()
        self.random = RandomIntuitionAgent()
        self.memory = ConversationMemory()
        self.leader_agent = Agent(
            name="coordenador_lider",
            model=OpenAIChat(id=model_id),
            instructions=[
                "Você é o Coordenador Líder de um sistema multi-agente de loteria.",
                "Responda em português do Brasil, de forma amigável e objetiva.",
                "Use os dados estruturados recebidos para produzir uma explicação curta.",
            ],
            markdown=True,
        )

    @staticmethod
    def _extract_games_requested(user_prompt: str) -> int:
        match = re.search(r"(\d+)", user_prompt)
        if not match:
            return 5
        amount = int(match.group(1))
        return max(1, min(15, amount))

    def _compose_candidate_pool(self, analysis: DrawAnalysis) -> list[int]:
        pool = set(analysis.hot_numbers[:10] + analysis.cold_numbers[:8] + analysis.repeated_numbers[:6])
        if len(pool) < 24:
            pool.update(range(1, 61))
        return sorted(pool)

    async def chat(self, session_id: str, prompt: str) -> dict[str, Any]:
        await self.memory.append(session_id, "user", prompt)
        requested_games = self._extract_games_requested(prompt)

        historical_analysis = await self.historical.analyze(prompt)
        random_games = await asyncio.to_thread(self.random.generate, requested_games)
        candidate_pool = self._compose_candidate_pool(historical_analysis)

        blended_games: list[list[int]] = []
        for g in random_games:
            mixed = sorted(set(g[:3] + candidate_pool[:3]))
            while len(mixed) < 6:
                mixed.append(secrets.SystemRandom().choice(candidate_pool))
                mixed = sorted(set(mixed))
            blended_games.append(mixed[:6])

        validated = [self.statistical.validate(game) for game in blended_games]
        validated = sorted(validated, key=lambda item: item["score_estatistico"], reverse=True)

        response_data = {
            "agente_historico": {
                "quentes": historical_analysis.hot_numbers[:10],
                "frios": historical_analysis.cold_numbers[:10],
                "padrao_pares_impares": historical_analysis.parity_distribution,
                "repeticoes": historical_analysis.repeated_numbers[:6],
            },
            "agente_estatistico": {
                "media_score": round(mean(v["score_estatistico"] for v in validated), 2) if validated else 0.0,
                "jogos_validados": validated,
            },
            "agente_intuicao": {
                "jogos_aleatorios_base": random_games,
            },
            "contexto_rag": historical_analysis.rag_context[:3000],
            "jogos_finais": [item["jogo"] for item in validated[:requested_games]],
        }

        leader_prompt = (
            "Consolide a análise multi-agente abaixo em um resumo amigável para o usuário. "
            f"Dados: {response_data}"
        )
        try:
            leader_text = await asyncio.to_thread(lambda: self.leader_agent.run(leader_prompt).content)
        except Exception:
            leader_text = (
                "Aqui está a consolidação dos especialistas. "
                f"Top jogos: {response_data['jogos_finais']}. "
                "Se quiser, posso gerar novas combinações com outro perfil de risco."
            )

        await self.memory.append(session_id, "assistant", leader_text)

        return {
            "session_id": session_id,
            "resumo": leader_text,
            "detalhes": response_data,
            "historico": await self.memory.history(session_id),
        }

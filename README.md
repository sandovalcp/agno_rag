# Chat Multi-Agente com Agno 2.5.2

Este projeto implementa um **chat multi-agente assíncrono** para sugestão de jogos, com:

- **Agente Analista Histórico**: lê PDFs da pasta `doc_pdf` e executa um RAG híbrido (relevância léxica + sinais de frequência).
- **Agente Estatístico**: valida combinações com desvio padrão, pares/ímpares, sequências diretas e distribuição por quadrantes.
- **Agente de Intuição Aleatória**: adiciona entropia com randomização segura (`secrets.SystemRandom`).
- **Agente Coordenador**: orquestra o fluxo e consolida uma resposta final amigável.

## Stack

- **Agno 2.5.2**
- **FastAPI** (API + interface web)
- **HTML/CSS/JS** (frontend simples)
- **Docker / Docker Compose**
- **100% assíncrono** no fluxo HTTP e orquestração principal
- **Memória conversacional por sessão**

## Estrutura principal

- `api.py`: servidor FastAPI e endpoints.
- `multi_agent_lottery.py`: implementação dos 4 agentes e memória.
- `templates/index.html`: interface web.
- `static/styles.css`: estilos da interface.
- `doc_pdf/`: pasta de PDFs usados no RAG híbrido.

## Como rodar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sua_chave"
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Acesse: `http://localhost:8000`

## Como rodar via Docker

```bash
docker compose up --build
```

Acesse: `http://localhost:8000`

## Endpoint principal

`POST /api/chat`

Payload:

```json
{
  "mensagem": "Quero 5 jogos equilibrados",
  "session_id": "opcional"
}
```

Retorno: resumo do coordenador, detalhes por agente, jogos finais e histórico da conversa.

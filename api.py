from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from multi_agent_lottery import LeaderCoordinatorAgent


app = FastAPI(title="Multi-Agente Loteria API", version="1.0.0")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

coordinator = LeaderCoordinatorAgent(model_id="gpt-4.1")


class ChatRequest(BaseModel):
    mensagem: str = Field(..., min_length=2)
    session_id: str | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> dict:
    session_id = payload.session_id or str(uuid.uuid4())
    return await coordinator.chat(session_id=session_id, prompt=payload.mensagem)

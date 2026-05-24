"""AI assistant REST routes."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from bionodulo.ai.assistant import chat_with_tools
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import AIChatRequest

ai_router = APIRouter()


def _get_registry(request: Request) -> Any:
    return request.app.state.node_registry


def _get_settings(request: Request) -> Any:
    return request.app.state.settings


def _get_settings_manager(request: Request) -> Any:
    return request.app.state.settings_manager


def _setting_literal(request: Request, key: str, default: Any = None) -> Any:
    sm = _get_settings_manager(request)
    try:
        settings = sm.get_all()
    except Exception:
        settings = {}
    return settings.get(key, default)


@ai_router.post("/ai/chat")
@limiter.limit("20/minute")
async def ai_chat(request: Request, body: AIChatRequest) -> dict[str, Any]:
    """Send a message to the AI assistant and get a tool-aware response."""
    settings = _get_settings(request)
    settings_manager = _get_settings_manager(request)
    registry = _get_registry(request)

    provider = body.provider or _setting_literal(request, "bionodulo.llm.provider", "openai")
    model = body.model or _setting_literal(request, "bionodulo.llm.model", None)
    api_key = _setting_literal(request, "bionodulo.llm.apiKey", "") or os.environ.get("OPENAI_API_KEY", "")
    api_base = _setting_literal(request, "bionodulo.llm.baseUrl", None) or None
    temperature = _setting_literal(request, "bionodulo.llm.temperature", 0.2)
    try:
        temperature = float(temperature)
    except (TypeError, ValueError):
        temperature = 0.2

    try:
        response = await chat_with_tools(
            user_message=body.message,
            workflow=body.workflow,
            workflow_id=body.workflow_id,
            history=body.history,
            provider=provider,
            model=model,
            api_key=api_key,
            api_base=api_base,
            temperature=temperature,
            registry=registry,
            settings=settings,
            settings_manager=settings_manager,
            files=[{"name": f.name, "mime_type": f.mime_type, "content": f.content} for f in body.files],
        )
    except Exception as exc:
        return {
            "steps": [{"type": "reply", "content": f"AI error: {exc}"}],
            "reply": f"AI error: {exc}",
            "model": model or provider,
        }

    return {
        "steps": [
            {
                "type": step.type,
                "content": step.content,
                "name": step.name,
                "arguments": step.arguments,
                "result": step.result,
                "workflow": step.workflow,
                "description": step.description,
            }
            for step in response.steps
        ],
        "reply": response.reply,
        "proposed_workflow": response.proposed_workflow,
        "proposed_description": response.proposed_description,
        "model": model or provider,
    }


@ai_router.post("/ai/chat/stream")
async def ai_chat_stream(request: Request, body: AIChatRequest) -> Any:
    """Stream an AI assistant response as server-sent events."""
    del request

    async def _stream() -> Any:
        chunks = [
            "AI assistant (streaming mode): ",
            "Analyzing your request... ",
            f"Message was: '{body.message}'. ",
            "Configure a real AI backend (OpenAI, Ollama, etc.) for production use.",
        ]
        for chunk in chunks:
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            await asyncio.sleep(0.1)
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")

"""AI assistant REST routes."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from bionodulo.ai.assistant import chat_with_tools
from bionodulo.ai.orchestrator import reproduce_paper
from bionodulo.api.app_state import app_state, setting_literal
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import AIChatRequest, AIReproducePaperRequest

ai_router = APIRouter()


def _get_registry(request: Request) -> Any:
    return request.app.state.node_registry


def _get_run_queue(request: Request) -> Any:
    return getattr(request.app.state, "run_queue", None)


def _llm_runtime_settings(request: Request, body: AIChatRequest) -> tuple[str, str | None, str | None, str | None, float, int]:
    provider = str(body.provider or setting_literal(request, "bionodulo.llm.provider", "openai") or "openai")
    model_value = body.model or setting_literal(request, "bionodulo.llm.model", None)
    model = str(model_value) if model_value else None
    api_key_value = setting_literal(request, "bionodulo.llm.apiKey", "")
    api_key = str(api_key_value).strip() or None
    api_base_value = setting_literal(request, "bionodulo.llm.baseUrl", None)
    api_base = str(api_base_value).strip() if api_base_value else None

    if provider.lower() == "litellm":
        api_key = api_key or os.environ.get("LITELLM_API_KEY") or None
        api_base = api_base or os.environ.get("BIONODULO_LITELLM_BASE_URL", "http://localhost:4000/v1")

    temperature_value = setting_literal(request, "bionodulo.llm.temperature", 0.2)
    try:
        temperature = float(temperature_value)
    except (TypeError, ValueError):
        temperature = 0.2

    max_tokens_value = setting_literal(request, "bionodulo.llm.maxTokens", 4096)
    try:
        max_tokens = int(max_tokens_value)
    except (TypeError, ValueError):
        max_tokens = 4096
    max_tokens = max(256, min(max_tokens, 32768))

    return provider, model, api_key, api_base, temperature, max_tokens


@ai_router.post("/ai/chat")
@limiter.limit("20/minute")
async def ai_chat(request: Request, body: AIChatRequest) -> dict[str, Any]:
    """Send a message to the AI assistant and get a tool-aware response."""
    state = app_state(request)
    settings = state.settings
    settings_manager = state.settings_manager
    registry = _get_registry(request)

    provider, model, api_key, api_base, temperature, max_tokens = _llm_runtime_settings(request, body)

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
            max_tokens=max_tokens,
            registry=registry,
            settings=settings,
            settings_manager=settings_manager,
            files=[{"name": f.name, "mime_type": f.mime_type, "content": f.content} for f in body.files],
            run_queue=_get_run_queue(request),
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
    """Stream an AI assistant response as server-sent events.

    Runs the full tool-aware chat (which is internally non-streaming because
    the LangGraph loop is round-based) and replays each ChatStep as its own
    SSE event. This gives the UI a progressive view without a graph rewrite:
    `tool_call`/`tool_result` events arrive as their rounds finish, and a
    final `reply` event closes the stream.
    """
    state = app_state(request)
    settings = state.settings
    settings_manager = state.settings_manager
    registry = _get_registry(request)

    provider, model, api_key, api_base, temperature, max_tokens = _llm_runtime_settings(request, body)

    async def _stream() -> Any:
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
                max_tokens=max_tokens,
                registry=registry,
                settings=settings,
                settings_manager=settings_manager,
                files=[{"name": f.name, "mime_type": f.mime_type, "content": f.content} for f in body.files],
                run_queue=_get_run_queue(request),
            )
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'reply', 'content': f'AI error: {exc}'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        for step in response.steps:
            payload = {
                "type": step.type,
                "content": step.content,
                "name": step.name,
                "arguments": step.arguments,
                "result": step.result,
                "workflow": step.workflow,
                "description": step.description,
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(_stream(), media_type="text/event-stream")


@ai_router.post("/ai/reproduce-paper")
@limiter.limit("3/minute")
async def ai_reproduce_paper(request: Request, body: AIReproducePaperRequest) -> dict[str, Any]:
    """Autonomously reproduce a paper's pipeline via parallel sub-agents.

    Parses the paper into a structured plan, then fans out dataset-acquisition
    and node-authoring sub-agents, builds the workflow, runs and debugs it, and
    verifies the outputs against the paper's claims.
    """
    state = app_state(request)
    settings = state.settings
    registry = _get_registry(request)
    provider, model, api_key, api_base, _temperature, _max_tokens = _llm_runtime_settings(request, body)

    try:
        report = await reproduce_paper(
            paper_text=body.paper_text,
            registry=registry,
            settings=settings,
            run_queue=_get_run_queue(request),
            provider=provider,
            model=model,
            api_key=api_key,
            api_base=api_base,
            workflow_id=body.workflow_id,
        )
    except Exception as exc:
        return {"error": f"Paper reproduction failed: {exc}"}
    return report

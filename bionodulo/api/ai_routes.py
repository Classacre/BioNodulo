"""AI assistant REST routes."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from bionodulo.ai.assistant import ChatStep, chat_with_tools
from bionodulo.ai.skills import list_skills
from bionodulo.ai.hosted import (
    HOSTED_MODEL,
    HOSTED_PROVIDER,
    bearer_from_headers,
    friendly_hosted_error,
    hosted_api_base,
    hosted_unavailable_reason,
    is_hosted_enabled,
)
from bionodulo.ai.orchestrator import reproduce_paper
from bionodulo.api.app_state import app_state, setting_literal
from bionodulo.api.rate_limits import limiter
from bionodulo.api.schemas import AIChatRequest, AIReproducePaperRequest

ai_router = APIRouter()


def _step_payload(step: ChatStep) -> dict[str, Any]:
    return {
        "type": step.type,
        "content": step.content,
        "name": step.name,
        "arguments": step.arguments,
        "result": step.result,
        "workflow": step.workflow,
        "description": step.description,
        "id": step.id,
        "status": step.status,
        "duration_ms": step.duration_ms,
    }


def _chat_error(exc: Exception, api_base: str | None) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return "The assistant timed out. Review its activity and try a smaller request."
    if api_base == hosted_api_base():
        return friendly_hosted_error(exc)
    return f"AI error: {exc}"


def _get_registry(request: Request) -> Any:
    return request.app.state.node_registry


def _get_run_queue(request: Request) -> Any:
    return getattr(request.app.state, "run_queue", None)


def _llm_runtime_settings(request: Request, body: AIChatRequest) -> tuple[str, str | None, str | None, str | None, float, int]:
    if app_state(request).cloud_settings.editor_mode:
        # The website supplies the authenticated caller's token separately from
        # AWS SigV4 Authorization. Never use shared settings/provider secrets or
        # caller-selected model endpoints in this multi-tenant process.
        token = bearer_from_headers({
            "authorization": request.headers.get("x-bionodulo-authorization", ""),
        })
        if not token or not is_hosted_enabled():
            raise HTTPException(status_code=401, detail=hosted_unavailable_reason())
        return HOSTED_PROVIDER, HOSTED_MODEL, token, hosted_api_base(), 0.2, 4096

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

    # Hosted assistant. Chosen only when the user has not configured a key of
    # their own, so "bring your own key" always wins and never silently routes
    # someone's prompts through our cloud. The model is pinned to the neutral
    # hosted label: the proxy substitutes the real hosted model, whose identity
    # is never exposed to the app.
    if api_key is None and not api_base and is_hosted_enabled():
        token = bearer_from_headers(request.headers)
        if token:
            provider = HOSTED_PROVIDER
            model = HOSTED_MODEL
            api_key = token
            api_base = hosted_api_base()

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

    # Neither a key of their own nor a signed-in session: say which of the two
    # is missing. Falling through leaves LiteLLM to raise "openai API key is
    # required", which is true and useless to someone who has never configured
    # a provider.
    if not api_key and provider.lower() not in {"custom", "litellm", "mock"}:
        raise HTTPException(status_code=401, detail=hosted_unavailable_reason())

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
        # Hosted mode: never leak the upstream provider or model — translate
        # quota exhaustion and outages into safe, actionable messages.
        message = _chat_error(exc, api_base)
        return {
            "steps": [_step_payload(ChatStep(type="error", content=message, status="error"))],
            "reply": "",
            "error": message,
            "model": model or provider,
        }

    return {
        "steps": [_step_payload(step) for step in response.steps],
        "reply": response.reply,
        "error": next((step.content for step in response.steps if step.type == "error"), None),
        "proposed_workflow": response.proposed_workflow,
        "proposed_description": response.proposed_description,
        "model": model or provider,
    }


@ai_router.post("/ai/chat/stream")
@limiter.limit("20/minute")
async def ai_chat_stream(request: Request, body: AIChatRequest) -> Any:
    """Stream an AI assistant response as server-sent events.

    The turn driver delivers steps into a queue while the request is running.
    """
    state = app_state(request)
    settings = state.settings
    settings_manager = state.settings_manager
    registry = _get_registry(request)

    provider, model, api_key, api_base, temperature, max_tokens = _llm_runtime_settings(request, body)

    async def _stream() -> Any:
        queue: asyncio.Queue[ChatStep | None] = asyncio.Queue()

        async def _run_chat() -> None:
            try:
                await chat_with_tools(
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
                    on_step=queue.put_nowait,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                queue.put_nowait(ChatStep(type="error", content=_chat_error(exc, api_base), status="error"))
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(_run_chat())
        elapsed = 0
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    step = await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    elapsed += 1
                    if elapsed >= 10:
                        yield ": heartbeat\n\n"
                        elapsed = 0
                    continue
                elapsed = 0
                if step is None:
                    yield "data: [DONE]\n\n"
                    break
                yield f"data: {json.dumps(_step_payload(step), default=str)}\n\n"
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    return StreamingResponse(_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@ai_router.get("/ai/skills")
async def ai_skills(request: Request) -> dict[str, Any]:
    """List available skill packs for the chat input's slash-command autocomplete.

    Cheap listing (name/description/source only, no bodies) whose names match
    the assistant's ``load_skill`` tool, so the UI can suggest valid
    ``/<skill-name>`` commands. Workspace skills are included when the app
    state carries a project root; bare apps (tests) list bundled + user packs.
    """
    settings = getattr(request.app.state, "settings", None)
    project_root = getattr(settings, "project_root", None)
    workspace = Path(project_root) if project_root else None
    return list_skills(workspace)


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
        if api_base == hosted_api_base():
            return {"error": friendly_hosted_error(exc)}
        return {"error": f"Paper reproduction failed: {exc}"}
    return report

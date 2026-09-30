"""Cancellable assistant turn driver, independent of model and tool adapters.

Only observable events are published. Provider reasoning is never inferred or
manufactured. Tool execution is sequential because graph edits share a draft.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class ChatStep:
    type: str
    content: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] | None = None
    description: str = ""
    id: str = ""
    status: str = ""
    duration_ms: int | None = None


@dataclass
class ChatResponse:
    steps: list[ChatStep]
    reply: str = ""
    proposed_workflow: dict[str, Any] | None = None
    proposed_description: str = ""


@dataclass
class ModelTurn:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def tool_failed(result: dict[str, Any]) -> bool:
    """Adapters may wrap a domain failure in a successful transport envelope."""
    inner = result.get("result")
    return bool(result.get("error")) or result.get("status") in {"error", "failed"} or (
        isinstance(inner, dict) and (
            bool(inner.get("error")) or inner.get("status") in {"error", "failed", "cancelled"}
        )
    )


async def run_turn(
    *,
    messages: list[dict[str, Any]],
    model: Callable[[list[dict[str, Any]], Callable[[str], None]], Awaitable[ModelTurn]],
    execute: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    allowed_tools: set[str],
    truncate: Callable[[str], str],
    on_step: Callable[[ChatStep], None] | None = None,
    max_rounds: int = 12,
    model_timeout: float = 90,
    tool_timeout: float = 45,
    request_timeout: float = 240,
) -> ChatResponse:
    response = ChatResponse(steps=[])
    failures: dict[str, int] = {}
    used_ids: set[str] = set()

    def emit(step: ChatStep, *, transient: bool = False) -> None:
        if not transient:
            response.steps.append(step)
        if on_step:
            on_step(step)

    def propose() -> None:
        if response.proposed_workflow is not None:
            emit(ChatStep(type="propose_changes", workflow=response.proposed_workflow,
                          description=response.proposed_description))

    async with asyncio.timeout(request_timeout):
        for round_index in range(max_rounds + 1):
            model_id = f"model_{round_index}_{uuid4().hex[:8]}"
            emit(ChatStep(type="status", content="Waiting for AI response…", id=model_id, status="running"))
            turn = await asyncio.wait_for(
                model(messages, lambda text: emit(
                    ChatStep(type="reply_delta", content=text, id=model_id), transient=True)),
                timeout=model_timeout,
            )
            if not turn.tool_calls:
                if not turn.content.strip():
                    raise RuntimeError("The model returned an empty response. Please retry.")
                response.reply = turn.content.strip()
                propose()
                emit(ChatStep(type="reply", content=response.reply, id=model_id, status="completed"))
                return response

            if turn.content.strip():
                emit(ChatStep(type="commentary", content=turn.content.strip(), id=model_id))
            if round_index == max_rounds:
                propose()
                emit(ChatStep(type="error", content="The assistant reached its tool-round limit. Review the activity and continue with a smaller request.", status="error"))
                return response

            # Complete all tool-result envelopes before the next model request.
            calls = []
            for call in turn.tool_calls:
                call = dict(call)
                call_id = str(call.get("id") or "")
                if not call_id or call_id in used_ids:
                    call_id = f"call_{uuid4().hex}"
                call["id"] = call_id
                used_ids.add(call_id)
                calls.append(call)
            messages.append({"role": "assistant", "content": turn.content, "tool_calls": [
                {"id": call["id"], "type": "function", "function": {
                    "name": call["name"], "arguments": json.dumps(call.get("arguments", {}), default=str),
                }} for call in calls
            ]})

            for call in calls:
                name, args, call_id = call["name"], call.get("arguments", {}), call["id"]
                emit(ChatStep(type="tool_call", name=name, arguments=args, id=call_id, status="running"))
                started = time.monotonic()
                result: dict[str, Any]
                if name not in allowed_tools:
                    result = {"status": "error", "error": "This tool is not available in this session."}
                elif call.get("parse_error"):
                    result = {"status": "error", "error": call["parse_error"]}
                else:
                    try:
                        result = await asyncio.wait_for(execute(name, args), timeout=tool_timeout)
                    except TimeoutError:
                        result = {"status": "error", "error": f"Tool {name} timed out. Its result is unconfirmed."}
                    except Exception:
                        result = {"status": "error", "error": f"Tool {name} failed. Review its inputs and try again."}
                failed = tool_failed(result)
                emit(ChatStep(type="tool_result", name=name, result=result, id=call_id,
                              status="error" if failed else "completed",
                              duration_ms=round((time.monotonic() - started) * 1000)))
                payload = result.get("result")
                workflow = payload.get("workflow") if isinstance(payload, dict) else None
                if not failed and result.get("mutates") is True and isinstance(workflow, dict):
                    response.proposed_workflow = workflow
                    response.proposed_description = "Review and apply the workflow changes drafted by the assistant."
                messages.append({"role": "tool", "tool_call_id": call_id, "name": name,
                                 "content": truncate(json.dumps(result, default=str))})
                fingerprint = name + json.dumps(args, sort_keys=True, default=str)
                failures[fingerprint] = failures.get(fingerprint, 0) + 1 if failed else 0
                if failures[fingerprint] >= 3:
                    propose()
                    emit(ChatStep(type="error", content=f"Stopped after the same {name} call failed three times. Review the tool errors before retrying.", status="error"))
                    return response
    return response

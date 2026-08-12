"""AI chat assistant for BioNodulo with tool-use capabilities.

Supports a reAct-style loop where the LLM can call tools to inspect
and modify workflows, environments, and settings.

File attachment handling:
- Images (PNG, JPEG, WEBP, GIF) are passed through native vision APIs.
- PDFs are sent as native document blocks to Anthropic; for OpenAI Chat
  Completions they are decoded to text where possible.
- Text/code files are decoded and included inline.
- Other binary files are described by metadata.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, TypedDict

from bionodulo.ai.tools import (
    ALL_TOOLS,
    ToolContext,
    aexecute_tool,
    tools_to_openai_schema,
)


BIONODULO_SYSTEM_PROMPT = '''You are BioNodulo AI, an expert bioinformatics workflow assistant integrated into the BioNodulo visual workbench.

BioNodulo is a node-based visual editor for building bioinformatics pipelines. Users drag nodes onto a canvas and connect them with edges. Each node represents a tool (e.g., FastQC, BWA, GATK) or data input. Nodes have typed inputs and outputs that must match when connected.

You are an autonomous agent, not just a chatbot. You can inspect, edit, RUN, and DEBUG workflows end to end:
- Inspect: `get_workflow_summary`, `get_node_info`, `list_available_nodes`, `validate_workflow`, `get_dependency_report`.
- Edit: `add_node`/`update_node`/`remove_node`/`add_edge`/`remove_edge`/`load_template` (drafted for the user to apply).
- Run: `run_workflow` executes the current workflow and returns per-node statuses. `read_run_logs` returns the log tail of a run; `get_run_status` and `get_run_history` track runs; `retry_run` re-submits one.
- Research: `search_literature` queries PubMed so method choices are grounded in papers.
- Extend: `write_custom_node` adds a Python node (with dependencies) for a tool the built-ins don't cover.
- Inspect data: `read_workspace_file` reads input/output files.

When debugging a failed run: call `run_workflow`, and if it fails, call `read_run_logs` for the failing node, diagnose the root cause, draft the fix, then run again — repeat until it succeeds or you are blocked.

When helping users:
- Use tools to fetch context rather than guessing.
- Prefer `get_workflow_summary` over `get_current_workflow` unless you need full parameters — it is much cheaper.
- For graph edits, the user confirms before they are applied. Running, installing, and writing files are actions you may take when the user has asked you to make the workflow work.
- Warn about common bioinformatics pitfalls (missing QC, wrong reference format, un-indexed references/VCFs, paired-end handling).
- Keep final replies plain text and concise, with concrete next steps.

Useful built-in nodes for visualization:
- `image_preview`: pin an image output (PNG/JPG/SVG) on the canvas.
- `html_preview`: pin an HTML report on the canvas (MultiQC, FastQC, plotly, etc.).
'''


# Per-task model routing. Frontier models for planning/diagnosis; the same tier
# is fine for tool-arg formatting today, but keep the seam so a cheaper model can
# be slotted in later. Provider-relative ids; resolved by ``_provider_model``.
DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4.1-mini",
    "openrouter": "openai/gpt-4.1-mini",
}


@dataclass
class ChatStep:
    """A single step in the AI reasoning chain."""

    type: str  # thinking, tool_call, tool_result, propose_changes, reply
    content: str = ""
    name: str = ""  # for tool_call: tool name
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    workflow: dict[str, Any] | None = None
    description: str = ""


@dataclass
class ChatResponse:
    """Full response from the AI assistant."""

    steps: list[ChatStep]
    reply: str = ""
    proposed_workflow: dict[str, Any] | None = None
    proposed_description: str = ""


# ---------------------------------------------------------------------------
# File handling helpers
# ---------------------------------------------------------------------------

def _parse_data_url(data_url: str) -> tuple[str, str]:
    """Parse a data URL into (mime_type, base64_data).

    Returns (application/octet-stream, raw_string) if not a data URL.
    """
    if data_url.startswith("data:"):
        try:
            header, data = data_url.split(",", 1)
            mime = header.split(";")[0].replace("data:", "")
            return mime, data
        except ValueError:
            pass
    return "application/octet-stream", data_url


# MIME types that each provider can handle natively as vision/images
_OPENAI_IMAGE_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}


def _decode_text_file(data_url: str) -> str | None:
    """Decode a data URL to UTF-8 text. Returns None on failure."""
    try:
        import base64
        _, b64 = _parse_data_url(data_url)
        return base64.b64decode(b64).decode("utf-8", errors="replace")
    except Exception:
        return None


def _extract_pdf_text(data_url: str, max_chars: int = 8000) -> str | None:
    """Best-effort PDF text extraction. Returns None if no extractor available."""
    try:
        import base64
        from io import BytesIO

        _, b64 = _parse_data_url(data_url)
        pdf_bytes = base64.b64decode(b64)

        # Markdown first: it keeps the headings and, crucially, the tables where
        # accessions, tool versions and parameters live. A page-by-page text
        # dump interleaves table cells into prose the model cannot read back.
        from bionodulo.ai.papers import to_markdown

        markdown = to_markdown(pdf_bytes, filename="paper.pdf", max_chars=max_chars)
        if markdown:
            return markdown

        # Try PyPDF2 first
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
                if len(text) >= max_chars:
                    break
            return text[:max_chars]
        except Exception:
            pass

        # Try pymupdf / fitz
        try:
            import fitz  # type: ignore
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
                if len(text) >= max_chars:
                    break
            doc.close()
            return text[:max_chars]
        except Exception:
            pass

        return None
    except Exception:
        return None


def _build_openai_content(
    user_message: str,
    files: list[dict[str, str]] | None,
) -> str | list[dict[str, Any]]:
    """Build OpenAI Chat Completions compatible message content.

    Images are sent as image_url blocks for native vision processing.
    Text files are decoded and inlined.
    PDFs undergo best-effort text extraction.
    """
    if not files:
        return user_message

    content: list[dict[str, Any]] = [{"type": "text", "text": user_message}]
    for f in files:
        name = f.get("name", "unknown")
        mime = f.get("mime_type", "application/octet-stream")
        data_url = f.get("content", "")

        if mime in _OPENAI_IMAGE_MIMES:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        elif mime == "application/pdf":
            pdf_text = _extract_pdf_text(data_url)
            if pdf_text:
                content.append({
                    "type": "text",
                    "text": f"\n--- PDF: {name} ---\n{pdf_text}\n--- End of PDF ---\n",
                })
            else:
                content.append({
                    "type": "text",
                    "text": f"\n[PDF file attached: {name}. Text extraction not available — install PyPDF2 or pymupdf for PDF support.]\n",
                })
        elif mime.startswith("text/") or mime in (
            "application/json",
            "application/yaml",
            "application/x-yaml",
            "application/javascript",
            "application/typescript",
            "application/x-sql",
            "application/xml",
        ):
            decoded = _decode_text_file(data_url)
            if decoded is not None:
                content.append({
                    "type": "text",
                    "text": f"\n--- File: {name} ({mime}) ---\n{decoded}\n--- End of {name} ---\n",
                })
            else:
                content.append({"type": "text", "text": f"\n[File: {name} — could not decode]\n"})
        else:
            content.append({
                "type": "text",
                "text": f"\n[Binary file attached: {name} ({mime})]\n",
            })
    return content


def _build_anthropic_content(
    user_message: str,
    files: list[dict[str, str]] | None,
) -> list[dict[str, Any]]:
    """Build Anthropic Messages API compatible content blocks.

    Images are sent as native image blocks.
    PDFs are sent as native document blocks.
    Text files are decoded and inlined.
    """
    content: list[dict[str, Any]] = [{"type": "text", "text": user_message}]
    if not files:
        return content

    for f in files:
        name = f.get("name", "unknown")
        mime = f.get("mime_type", "application/octet-stream")
        data_url = f.get("content", "")

        if mime.startswith("image/"):
            media_type, b64 = _parse_data_url(data_url)
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type or mime, "data": b64},
            })
        elif mime == "application/pdf":
            _, b64 = _parse_data_url(data_url)
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })
        elif mime.startswith("text/") or mime in (
            "application/json",
            "application/yaml",
            "application/x-yaml",
            "application/javascript",
            "application/typescript",
            "application/x-sql",
            "application/xml",
        ):
            decoded = _decode_text_file(data_url)
            if decoded is not None:
                content.append({
                    "type": "text",
                    "text": f"\n--- File: {name} ({mime}) ---\n{decoded}\n--- End of {name} ---\n",
                })
            else:
                content.append({"type": "text", "text": f"\n[File: {name} — could not decode]\n"})
        else:
            content.append({
                "type": "text",
                "text": f"\n[Binary file attached: {name} ({mime})]\n",
            })
    return content


def _convert_message_for_anthropic(msg: dict[str, Any]) -> dict[str, Any]:
    """Convert a single message from OpenAI-format content to Anthropic format.

    Anthropic uses slightly different block types for images.
    """
    raw_content = msg.get("content")
    if isinstance(raw_content, str) or raw_content is None:
        return msg

    new_content: list[dict[str, Any]] = []
    for part in raw_content:
        ptype = part.get("type")
        if ptype == "text":
            new_content.append({"type": "text", "text": part.get("text", "")})
        elif ptype == "image_url":
            url = part.get("image_url", {}).get("url", "")
            if url.startswith("data:"):
                media_type, b64 = _parse_data_url(url)
                new_content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type or "image/png", "data": b64},
                })
            else:
                new_content.append({
                    "type": "image",
                    "source": {"type": "url", "url": url},
                })
        elif ptype == "document":
            # Already in Anthropic format
            new_content.append(part)
        else:
            # Fallback: stringify unknown parts
            new_content.append({"type": "text", "text": str(part)})
    return {**msg, "content": new_content}


# ---------------------------------------------------------------------------
# LLM backend
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _provider_model(provider: str, model: str | None) -> str:
    provider = provider.lower()
    if provider == "anthropic":
        chosen = model or DEFAULT_MODELS["anthropic"]
        return chosen if chosen.startswith("anthropic/") else f"anthropic/{chosen}"
    if provider == "openrouter":
        chosen = model or DEFAULT_MODELS["openrouter"]
        return chosen if chosen.startswith("openrouter/") else f"openrouter/{chosen}"
    return model or DEFAULT_MODELS["openai"]


def _provider_api_key(provider: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    normalized = provider.lower()
    if normalized == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    if normalized == "openrouter":
        return os.environ.get("OPENROUTER_API_KEY", "")
    if normalized in {"custom", "litellm"}:
        return os.environ.get("LITELLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    return os.environ.get("OPENAI_API_KEY", "")


def _parse_tool_call(call: Any) -> dict[str, Any] | None:
    function = _obj_get(call, "function", {})
    name = _obj_get(function, "name", "")
    if not name:
        return None
    raw_args = _obj_get(function, "arguments", "{}")
    if isinstance(raw_args, str):
        try:
            arguments = json.loads(raw_args or "{}")
        except json.JSONDecodeError:
            arguments = {}
    elif isinstance(raw_args, dict):
        arguments = raw_args
    else:
        arguments = {}
    return {
        "id": str(_obj_get(call, "id", f"call_{name}")),
        "type": str(_obj_get(call, "type", "function")),
        "name": str(name),
        "arguments": arguments if isinstance(arguments, dict) else {},
    }


def _assistant_tool_call_message(content: str, tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call.get("arguments", {}), default=str),
                },
            }
            for call in tool_calls
        ],
    }


async def _call_llm(
    messages: list[dict[str, Any]],
    provider: str,
    model: str | None,
    api_key: str | None,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
    tools: list[dict[str, Any]] | None = None,
) -> LLMResponse:
    if not api_key and provider not in {"custom", "litellm"}:
        raise ValueError(f"{provider} API key is required.")
    import litellm

    kwargs: dict[str, Any] = {
        "model": _provider_model(provider, model),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    try:
        response = await litellm.acompletion(**kwargs)
    except Exception as exc:
        # Reasoning models reject `temperature` outright ("deprecated for this
        # model"). Which ones do is the provider's business and changes without
        # notice, so react to the refusal rather than keep a list that goes
        # stale and takes the assistant down with it.
        if "temperature" in str(exc).lower() and "temperature" in kwargs:
            kwargs.pop("temperature")
            try:
                response = await litellm.acompletion(**kwargs)
            except Exception as retry_exc:
                raise RuntimeError(f"LLM provider error: {retry_exc}") from retry_exc
        else:
            raise RuntimeError(f"LLM provider error: {exc}") from exc

    choices = _obj_get(response, "choices", [])
    if not choices:
        return LLMResponse(content="")
    message = _obj_get(choices[0], "message", {})
    content = _obj_get(message, "content", "") or ""
    raw_tool_calls = _obj_get(message, "tool_calls", []) or []
    tool_calls = [
        parsed
        for parsed in (_parse_tool_call(call) for call in raw_tool_calls)
        if parsed is not None
    ]
    return LLMResponse(content=str(content), tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------

# The agent loop can run a workflow, read its logs, fix the graph, and re-run.
# Autonomous debugging needs more than a couple of rounds, so the budget is
# generous; cost is bounded by history trimming + tool-result truncation below.
#: Tool-use rounds before the loop gives up.
#:
#: Interactive chat rarely needs more than a handful, but reproducing a paper
#: builds a node and an edge at a time: an eight-step pipeline is already ~15
#: calls before validation, and hitting the cap mid-build leaves a half-wired
#: graph. Callers that orchestrate multi-step builds raise it via
#: ``max_tool_rounds``.
MAX_TOOL_ROUNDS = 12

# Token-efficiency knobs. The assistant loop sends the FULL message list on
# every iteration, so trimming what we send is the single biggest cost lever.
#
# - HISTORY_TURN_LIMIT keeps the most recent N user/assistant turns from the
#   prior conversation. Older turns are dropped before we hit the LLM.
# - TOOL_RESULT_MAX_BYTES truncates large tool results (e.g. a full workflow
#   JSON) before they go back into the message list. We keep the head so the
#   LLM still sees structure and append a trailing marker.
HISTORY_TURN_LIMIT = 12
TOOL_RESULT_MAX_BYTES = 8000


def _trim_history(history: list[dict[str, Any]], limit: int = HISTORY_TURN_LIMIT) -> list[dict[str, Any]]:
    """Keep the last `limit` non-system turns from the conversation."""
    non_system = [msg for msg in history if msg.get("role") != "system"]
    if len(non_system) <= limit:
        return non_system
    return non_system[-limit:]


def _truncate_tool_payload(payload: str, max_bytes: int = TOOL_RESULT_MAX_BYTES) -> str:
    """Truncate a JSON-encoded tool result that is too large to send back."""
    if len(payload) <= max_bytes:
        return payload
    head = payload[: max_bytes - 80]
    return f"{head}\n... [truncated {len(payload) - len(head)} bytes — call a more specific tool if you need the rest]"



class AssistantGraphState(TypedDict, total=False):
    """Mutable state passed through the LangGraph assistant workflow."""

    messages: list[dict[str, Any]]
    steps: list[ChatStep]
    ctx: ToolContext
    tool_calls: list[dict[str, Any]]
    last_content: str
    mutated_workflow: bool
    proposed_workflow: dict[str, Any] | None
    proposed_description: str
    reply: str
    rounds: int
    error: str
    provider: str
    model: str | None
    api_key: str | None
    api_base: str | None
    temperature: float
    max_tokens: int
    tool_schemas: list[dict[str, Any]]


async def _graph_call_model(state: AssistantGraphState) -> AssistantGraphState:
    messages_state = list(state["messages"])
    steps_state = list(state.get("steps", []))
    try:
        llm_response = await _call_llm(
            messages=messages_state,
            provider=state["provider"],
            model=state.get("model"),
            api_key=_provider_api_key(state["provider"], state.get("api_key")),
            api_base=state.get("api_base"),
            temperature=state["temperature"],
            max_tokens=state["max_tokens"],
            tools=state["tool_schemas"],
        )
    except Exception as exc:
        reply = f"Sorry, I encountered an error: {exc}"
        steps_state.append(ChatStep(type="reply", content=reply))
        return {"steps": steps_state, "reply": reply, "error": reply}

    content = llm_response.content
    tool_calls = llm_response.tool_calls
    updates: AssistantGraphState = {
        "steps": steps_state,
        "last_content": content,
        "tool_calls": tool_calls,
    }
    if tool_calls:
        return updates

    proposed_workflow = state.get("proposed_workflow")
    proposed_description = state.get("proposed_description", "")
    if state.get("mutated_workflow"):
        graph_ctx = state["ctx"]
        proposed_workflow = graph_ctx.workflow
        proposed_description = "Apply the workflow changes drafted by the assistant tools."
        steps_state.append(
            ChatStep(
                type="propose_changes",
                workflow=proposed_workflow,
                description=proposed_description,
            )
        )
    reply = content.strip()
    if reply:
        steps_state.append(ChatStep(type="reply", content=reply))
    updates.update(
        {
            "steps": steps_state,
            "reply": reply,
            "proposed_workflow": proposed_workflow,
            "proposed_description": proposed_description,
        }
    )
    return updates


async def _graph_run_tool(state: AssistantGraphState) -> AssistantGraphState:
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        return {}

    steps_state = list(state.get("steps", []))
    messages_state = list(state["messages"])
    messages_state.append(_assistant_tool_call_message(state.get("last_content", ""), tool_calls))
    graph_ctx = state["ctx"]
    mutated = bool(state.get("mutated_workflow"))

    for tool_call in tool_calls:
        tool_name = str(tool_call.get("name", ""))
        args = tool_call.get("arguments", {})
        if not isinstance(args, dict):
            args = {}

        steps_state.append(ChatStep(type="tool_call", name=tool_name, arguments=args))

        result = await aexecute_tool(tool_name, args, graph_ctx)

        steps_state.append(
            ChatStep(
                type="tool_result",
                name=tool_name,
                result=result,
            )
        )

        if isinstance(result, dict) and result.get("status") == "ok":
            inner = result.get("result", {})
            if isinstance(inner, dict) and "workflow" in inner:
                graph_ctx.workflow = inner["workflow"]
                mutated = True

        messages_state.append(
            {
                "role": "tool",
                "tool_call_id": str(tool_call.get("id", f"call_{tool_name}")),
                "name": tool_name,
                "content": _truncate_tool_payload(json.dumps(result, default=str)),
            }
        )

    return {
        "messages": messages_state,
        "steps": steps_state,
        "ctx": graph_ctx,
        "mutated_workflow": mutated,
        "rounds": int(state.get("rounds", 0)) + 1,
        "tool_calls": [],
    }


def _route_after_model(state: AssistantGraphState) -> str:
    if state.get("error"):
        return "__end__"
    if state.get("tool_calls") and int(state.get("rounds", 0)) < int(
        state.get("max_tool_rounds") or MAX_TOOL_ROUNDS
    ):
        return "tool"
    return "__end__"


@lru_cache(maxsize=1)
def _compiled_assistant_graph() -> Any:
    """Compile the LangGraph assistant once per process."""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(AssistantGraphState)
    graph.add_node("model", _graph_call_model)
    graph.add_node("tool", _graph_run_tool)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", _route_after_model, {"tool": "tool", "__end__": END})
    graph.add_edge("tool", "model")
    return graph.compile()


async def chat_with_tools(
    user_message: str,
    workflow: dict[str, Any] | None,
    history: list[dict[str, str]],
    workflow_id: str | None = None,
    provider: str = "openai",
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    registry: Any = None,
    settings: Any = None,
    settings_manager: Any = None,
    files: list[dict[str, str]] | None = None,
    run_queue: Any = None,
    system_prompt: str | None = None,
    tool_names: list[str] | None = None,
    max_tool_rounds: int | None = None,
) -> ChatResponse:
    """Run the AI chat with a tool-use loop.

    Returns a ChatResponse containing all reasoning steps, tool calls,
    and optionally a proposed workflow change for user confirmation.

    ``system_prompt`` overrides the default assistant persona (used to spawn
    focused sub-agents), and ``tool_names`` restricts the tools offered to a
    subset of :data:`ALL_TOOLS` (e.g. a dataset sub-agent only needs research +
    download + file tools).
    """
    ctx = ToolContext(
        workflow=workflow,
        workflow_id=workflow_id,
        registry=registry,
        settings=settings,
        settings_manager=settings_manager,
        run_queue=run_queue,
    )
    if tool_names:
        wanted = set(tool_names)
        active_tools = [tool for tool in ALL_TOOLS if tool.name in wanted]
    else:
        active_tools = ALL_TOOLS
    tool_schemas = tools_to_openai_schema(active_tools)
    system_prompt = system_prompt or BIONODULO_SYSTEM_PROMPT

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    # Drop older history beyond HISTORY_TURN_LIMIT so the prefill stays small.
    # Each tool round already re-sends the entire message list, so old turns
    # are by far the biggest dead-weight in long sessions.
    for msg in _trim_history(history):
        messages.append(dict(msg))

    user_content: str | list[dict[str, Any]] = _build_openai_content(user_message, files)

    messages.append({"role": "user", "content": user_content})

    compiled = _compiled_assistant_graph()

    final_state = await compiled.ainvoke(
        {
            "messages": messages,
            "steps": [],
            "ctx": ctx,
            "tool_calls": [],
            "mutated_workflow": False,
            "proposed_workflow": None,
            "proposed_description": "",
            "reply": "",
            "rounds": 0,
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "api_base": api_base,
            "temperature": temperature,
            "max_tool_rounds": int(max_tool_rounds or MAX_TOOL_ROUNDS),
            "max_tokens": max_tokens,
            "tool_schemas": tool_schemas,
        }
    )

    steps = list(final_state.get("steps", []))
    proposed_workflow = final_state.get("proposed_workflow")
    proposed_description = final_state.get("proposed_description", "")
    reply = final_state.get("reply", "")

    if final_state.get("tool_calls") and int(final_state.get("rounds", 0)) >= int(
        final_state.get("max_tool_rounds") or MAX_TOOL_ROUNDS
    ):
        if final_state.get("mutated_workflow"):
            graph_ctx = final_state["ctx"]
            proposed_workflow = graph_ctx.workflow
            proposed_description = "Apply the workflow changes drafted by the assistant tools."
            steps.append(
                ChatStep(
                    type="propose_changes",
                    workflow=proposed_workflow,
                    description=proposed_description,
                )
            )
        reply = "I reached the maximum number of tool calls. Please simplify your request."
        steps.append(ChatStep(type="reply", content=reply))

    return ChatResponse(
        steps=steps,
        reply=reply,
        proposed_workflow=proposed_workflow,
        proposed_description=proposed_description,
    )

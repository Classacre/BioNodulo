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
import re as re_mod
from dataclasses import dataclass, field
from typing import Any, TypedDict

from bionodulo.ai.tools import (
    ALL_TOOLS,
    ToolContext,
    execute_tool,
    format_tools_for_prompt,
)


BIONODULO_SYSTEM_PROMPT = '''You are BioNodulo AI, an expert bioinformatics workflow assistant integrated into the BioNodulo visual workbench.

BioNodulo is a node-based visual editor for building bioinformatics pipelines. Users drag nodes onto a canvas and connect them with edges. Each node represents a tool (e.g., FastQC, BWA, GATK) or data input. Nodes have typed inputs and outputs that must match when connected.

When helping users:
- Ask clarifying questions if the request is vague
- Use tools to fetch context rather than guessing
- Explain your reasoning with <thinking> tags
- Propose concrete, step-by-step workflow changes
- Warn about common bioinformatics pitfalls (missing QC, wrong reference format, etc.)
- If the user attaches files, analyze their contents and reference them in your answer

{tools_text}

Response format rules:
1. When you need information, use a <tool_call>.
2. Show your reasoning in <thinking> tags BEFORE each tool call.
3. After gathering information, you may propose changes with <propose_changes>.
4. For your final response to the user, write plain text (no tags needed).
5. You can make multiple tool calls in sequence; wait for each result before the next.
'''


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
# Parsing
# ---------------------------------------------------------------------------

_TOOL_CALL_RE = re_mod.compile(r'<tool_call\s+name="([^"]+)">\s*(.*?)\s*</tool_call>', re_mod.DOTALL)
_THINKING_RE = re_mod.compile(r'<thinking>\s*(.*?)\s*</thinking>', re_mod.DOTALL)
_PROPOSE_RE = re_mod.compile(r'<propose_changes>\s*(.*?)\s*</propose_changes>', re_mod.DOTALL)


def _extract_tool_calls(text: str) -> list[dict[str, Any]]:
    calls = []
    for match in _TOOL_CALL_RE.finditer(text):
        name = match.group(1)
        args_str = match.group(2).strip()
        try:
            args = json.loads(args_str) if args_str else {}
        except json.JSONDecodeError:
            args = {}
        calls.append({"name": name, "arguments": args})
    return calls


def _extract_thinking(text: str) -> str:
    parts = []
    for match in _THINKING_RE.finditer(text):
        parts.append(match.group(1).strip())
    return "\n\n".join(parts)


def _extract_propose_changes(text: str) -> dict[str, Any] | None:
    for match in _PROPOSE_RE.finditer(text):
        try:
            data = json.loads(match.group(1).strip())
            return data
        except json.JSONDecodeError:
            continue
    return None


def _strip_tags(text: str) -> str:
    text = _TOOL_CALL_RE.sub("", text)
    text = _THINKING_RE.sub("", text)
    text = _PROPOSE_RE.sub("", text)
    text = re_mod.sub(r"\n{3,}", "\n\n", text).strip()
    return text


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

async def _call_llm(
    messages: list[dict[str, Any]],
    provider: str,
    model: str | None,
    api_key: str | None,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    if provider in ("openai", "custom"):
        return await _call_openai(
            messages, model or "gpt-4", api_key or "", api_base, temperature, max_tokens
        )
    elif provider == "anthropic":
        return await _call_anthropic(
            messages, model or "claude-3-sonnet-20240229", api_key or "", api_base, temperature, max_tokens
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


async def _call_openai(
    messages: list[dict[str, Any]],
    model: str,
    api_key: str,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    if not api_key:
        raise ValueError("OpenAI API key is required.")
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required. pip install httpx")

    base_url = api_base or "https://api.openai.com/v1"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(
    messages: list[dict[str, Any]],
    model: str,
    api_key: str,
    api_base: str | None,
    temperature: float,
    max_tokens: int,
) -> str:
    if not api_key:
        raise ValueError("Anthropic API key is required.")
    try:
        import httpx
    except ImportError:
        raise RuntimeError("httpx is required. pip install httpx")

    system_content = ""
    conversation: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_content += (msg.get("content") or "") + "\n"
        else:
            conversation.append(_convert_message_for_anthropic(msg))

    base_url = api_base or "https://api.anthropic.com"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": conversation,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if system_content:
        payload["system"] = system_content.strip()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json=payload,
            timeout=120.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API error {response.status_code}: {response.text}")
        data = response.json()
        return data["content"][0]["text"]


# ---------------------------------------------------------------------------
# Main chat loop
# ---------------------------------------------------------------------------

MAX_TOOL_ROUNDS = 6


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


def _tool_param_type(type_name: str) -> Any:
    """Map BioNodulo tool parameter names to Pydantic-friendly Python types."""
    normalized = type_name.lower()
    if normalized in {"int", "integer"}:
        return int
    if normalized in {"float", "number"}:
        return float
    if normalized in {"bool", "boolean"}:
        return bool
    if normalized in {"array", "list"}:
        return list[Any]
    if normalized in {"object", "dict", "json"}:
        return dict[str, Any]
    return str


def _build_langchain_tools(ctx: ToolContext) -> dict[str, Any]:
    """Wrap existing BioNodulo tools as LangChain StructuredTool instances."""
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    wrapped: dict[str, Any] = {}
    for definition in ALL_TOOLS:
        fields: dict[str, Any] = {}
        for param in definition.parameters:
            py_type = _tool_param_type(param.type)
            if param.required:
                fields[param.name] = (
                    py_type,
                    Field(description=param.description),
                )
            else:
                fields[param.name] = (
                    py_type | None,
                    Field(default=param.default, description=param.description),
                )
        args_schema = create_model(f"{definition.name}_Args", **fields)

        def _runner(_tool_name: str = definition.name, **kwargs: Any) -> dict[str, Any]:
            return execute_tool(_tool_name, kwargs, ctx)

        _runner.__name__ = f"run_{definition.name}"
        wrapped[definition.name] = StructuredTool.from_function(
            func=_runner,
            name=definition.name,
            description=definition.description,
            args_schema=args_schema,
        )
    return wrapped


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
) -> ChatResponse:
    """Run the AI chat with a tool-use loop.

    Returns a ChatResponse containing all reasoning steps, tool calls,
    and optionally a proposed workflow change for user confirmation.
    """
    ctx = ToolContext(
        workflow=workflow,
        workflow_id=workflow_id,
        registry=registry,
        settings=settings,
        settings_manager=settings_manager,
    )
    tools_text = format_tools_for_prompt(ALL_TOOLS)
    system_prompt = BIONODULO_SYSTEM_PROMPT.format(tools_text=tools_text)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    # Add history (skip system messages)
    for msg in history:
        if msg.get("role") != "system":
            messages.append(dict(msg))

    # Build provider-specific user message content
    if provider == "anthropic":
        user_content: str | list[dict[str, Any]] = _build_anthropic_content(user_message, files)
    else:
        user_content = _build_openai_content(user_message, files)

    messages.append({"role": "user", "content": user_content})

    from langgraph.graph import END, StateGraph

    langchain_tools = _build_langchain_tools(ctx)

    async def call_model(state: AssistantGraphState) -> AssistantGraphState:
        messages_state = list(state["messages"])
        steps_state = list(state.get("steps", []))
        try:
            content = await _call_llm(
                messages=messages_state,
                provider=provider,
                model=model,
                api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
                api_base=api_base,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            reply = f"Sorry, I encountered an error: {exc}"
            steps_state.append(ChatStep(type="reply", content=reply))
            return {"steps": steps_state, "reply": reply, "error": reply}

        thinking = _extract_thinking(content)
        if thinking:
            steps_state.append(ChatStep(type="thinking", content=thinking))

        tool_calls = _extract_tool_calls(content)
        updates: AssistantGraphState = {
            "steps": steps_state,
            "last_content": content,
            "tool_calls": tool_calls,
        }
        if tool_calls:
            return updates

        propose = _extract_propose_changes(content)
        proposed_workflow = state.get("proposed_workflow")
        proposed_description = state.get("proposed_description", "")
        if propose:
            proposed_workflow = propose.get("workflow")
            proposed_description = propose.get("description", "")
            steps_state.append(
                ChatStep(
                    type="propose_changes",
                    workflow=proposed_workflow,
                    description=proposed_description,
                )
            )
        elif state.get("mutated_workflow"):
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
        reply = _strip_tags(content)
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

    async def run_tool(state: AssistantGraphState) -> AssistantGraphState:
        tool_calls = state.get("tool_calls", [])
        if not tool_calls:
            return {}
        tool_call = tool_calls[0]
        tool_name = str(tool_call.get("name", ""))
        args = tool_call.get("arguments", {})
        if not isinstance(args, dict):
            args = {}

        steps_state = list(state.get("steps", []))
        steps_state.append(ChatStep(type="tool_call", name=tool_name, arguments=args))

        tool = langchain_tools.get(tool_name)
        if tool is None:
            result = {"status": "error", "error": f"Unknown tool: {tool_name}"}
        else:
            try:
                result = tool.invoke(args)
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}

        steps_state.append(
            ChatStep(
                type="tool_result",
                name=tool_name,
                result=result,
            )
        )

        graph_ctx = state["ctx"]
        mutated = bool(state.get("mutated_workflow"))
        if isinstance(result, dict) and result.get("status") == "ok":
            inner = result.get("result", {})
            if isinstance(inner, dict) and "workflow" in inner:
                graph_ctx.workflow = inner["workflow"]
                mutated = True

        result_text = json.dumps(result, default=str, indent=2)
        messages_state = list(state["messages"])
        messages_state.append({"role": "assistant", "content": state.get("last_content", "")})
        messages_state.append(
            {
                "role": "user",
                "content": f"Tool result for {tool_name}:\n{result_text}",
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

    def route_after_model(state: AssistantGraphState) -> str:
        if state.get("error"):
            return END
        if state.get("tool_calls") and int(state.get("rounds", 0)) < MAX_TOOL_ROUNDS:
            return "tool"
        return END

    graph = StateGraph(AssistantGraphState)
    graph.add_node("model", call_model)
    graph.add_node("tool", run_tool)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", route_after_model, {"tool": "tool", END: END})
    graph.add_edge("tool", "model")
    compiled = graph.compile()

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
        }
    )

    steps = list(final_state.get("steps", []))
    proposed_workflow = final_state.get("proposed_workflow")
    proposed_description = final_state.get("proposed_description", "")
    reply = final_state.get("reply", "")

    if final_state.get("tool_calls") and int(final_state.get("rounds", 0)) >= MAX_TOOL_ROUNDS:
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

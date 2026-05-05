from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from bionodulo.api.schemas import AIChatRequest
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow
from bionodulo.workflow.validation import validate_workflow


SYSTEM_PROMPT = """You are the BioNodulo workflow assistant.
Help scientists build reproducible bioinformatics workflows on a visual node canvas.
You can read the current workflow JSON, BioNodulo documentation, and node registry metadata.

Return one JSON object only, with this shape:
{
  "reply": "short helpful explanation for the user",
  "workflow": optional complete BioNodulo workflow JSON if you changed or created a workflow,
  "node_blueprint": optional object describing a new node class to create later
}

Rules:
- Keep workflow JSON valid for BioNodulo's schema: app, version, nodes, edges, outputs, environment.
- Use registered node ids unless you are explicitly proposing a custom node blueprint.
- Preserve existing node ids when editing existing workflows unless a replacement is necessary.
- Prefer simple, inspectable workflows over clever abstractions.
- Include environment metadata when a workflow depends on external tools.
- Do not invent installed tools. Use mock mode friendly examples when possible.
"""


async def chat_with_assistant(payload: AIChatRequest, registry: NodeRegistry, project_root: Path) -> dict[str, Any]:
    docs = _documentation_context(project_root)
    registry_context = _registry_context(registry)
    workflow_json = json.dumps(payload.workflow.model_dump(mode="json"), indent=2)
    context = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Project documentation:\n{docs}\n\n"
        f"Registered node metadata:\n{registry_context}\n\n"
        f"Current workflow JSON:\n{workflow_json}"
    )
    settings = payload.settings
    if not settings.api_key.strip():
        return _local_response(payload.workflow)

    if settings.provider == "gemini":
        raw_text = await _call_gemini(settings.model, settings.api_key, settings.temperature, context, payload.messages)
    else:
        raw_text = await _call_chat_completions(settings.provider, settings.model, settings.api_key, settings.base_url, settings.temperature, context, payload.messages)
    parsed = _parse_structured_response(raw_text)
    return _normalize_ai_response(parsed, raw_text=raw_text, registry=registry, project_root=project_root)


def _local_response(workflow: Workflow) -> dict[str, Any]:
    return {
        "reply": (
            "AI chat is ready. Add an API key in Settings to let a provider read the project docs, "
            "node registry, and this workflow. I can then propose valid workflow JSON for you to apply."
        ),
        "workflow": None,
        "node_blueprint": None,
        "raw_text": "",
        "validation": None,
        "provider": "local",
    }


async def _call_chat_completions(provider: str, model: str, api_key: str, base_url: str, temperature: float, context: str, messages: list) -> str:
    url = _chat_completions_url(provider, base_url)
    request_messages = [{"role": "system", "content": context}]
    request_messages.extend({"role": message.role, "content": message.content} for message in messages)
    body = {
        "model": model,
        "messages": request_messages,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "http://127.0.0.1:8000"
        headers["X-Title"] = "BioNodulo"
    data = await _post_json(url, body, headers)
    return data["choices"][0]["message"]["content"]


async def _call_gemini(model: str, api_key: str, temperature: float, context: str, messages: list) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    transcript = "\n\n".join(f"{message.role}: {message.content}" for message in messages)
    body = {
        "contents": [{"role": "user", "parts": [{"text": f"{context}\n\nConversation:\n{transcript}"}]}],
        "generationConfig": {"temperature": temperature},
    }
    data = await _post_json(url, body, {"Content-Type": "application/json"})
    parts = data["candidates"][0]["content"].get("parts", [])
    return "\n".join(part.get("text", "") for part in parts).strip()


async def _post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    def send() -> dict[str, Any]:
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM provider returned HTTP {exc.code}: {detail[:1200]}") from exc

    return await asyncio.to_thread(send)


def _chat_completions_url(provider: str, base_url: str) -> str:
    if base_url.strip():
        cleaned = base_url.rstrip("/")
        if cleaned.endswith("/chat/completions"):
            return cleaned
        return f"{cleaned}/chat/completions"
    if provider == "openrouter":
        return "https://openrouter.ai/api/v1/chat/completions"
    return "https://api.openai.com/v1/chat/completions"


def _documentation_context(project_root: Path) -> str:
    paths = [project_root / "README.md", *(project_root / "docs").glob("*.md")]
    chunks = []
    for path in paths:
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            chunks.append(f"# {path.relative_to(project_root)}\n{text[:5000]}")
    return "\n\n".join(chunks)[:18000]


def _registry_context(registry: NodeRegistry) -> str:
    compact = {}
    for node_id, meta in registry.object_info().items():
        compact[node_id] = {
            "display_name": meta.get("display_name"),
            "category": meta.get("category"),
            "inputs": meta.get("inputs"),
            "outputs": meta.get("outputs"),
            "search_aliases": meta.get("search_aliases"),
            "requires_external_tools": meta.get("requires_external_tools"),
            "required_executables": meta.get("required_executables"),
            "output_node": meta.get("output_node"),
        }
    return json.dumps(compact, indent=2)[:18000]


def _parse_structured_response(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {"reply": text.strip()}


def _normalize_ai_response(parsed: dict[str, Any], *, raw_text: str, registry: NodeRegistry, project_root: Path) -> dict[str, Any]:
    workflow = parsed.get("workflow")
    validation = None
    if workflow:
        try:
            candidate = Workflow.model_validate(workflow)
            validation = validate_workflow(candidate, registry, mock_tools=True, project_root=project_root).model_dump()
            workflow = candidate.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - shown directly to user as model-output validation feedback.
            validation = {"valid": False, "errors": [{"level": "error", "code": "ai_workflow_invalid", "message": str(exc)}], "warnings": []}
    return {
        "reply": str(parsed.get("reply") or parsed.get("message") or raw_text).strip(),
        "workflow": workflow,
        "node_blueprint": parsed.get("node_blueprint"),
        "raw_text": raw_text,
        "validation": validation,
        "provider": "llm",
    }

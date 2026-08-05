"""Shared LLM backend for workflow AI nodes."""
from __future__ import annotations

import json
import os
import re
import asyncio
from dataclasses import dataclass, field
from typing import Any

from bionodulo.core.credentials import resolve_secret_value


@dataclass(frozen=True)
class LLMConfig:
    """Resolved LiteLLM call configuration."""

    provider: str = "openai"
    model: str = "openai/gpt-4.1-mini"
    api_key: str = ""
    api_base: str = ""
    #: ``None`` omits the parameter entirely. Reasoning models reject it --
    #: Claude 4.6+ answers "`temperature` is deprecated for this model" -- so a
    #: fixed default would make those models unusable.
    temperature: float | None = 0.2
    max_tokens: int = 1024
    timeout: float = 60.0


@dataclass
class LLMResponse:
    """Normalized LLM completion response."""

    content: str
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = ""
    error: str = ""
    raw_response: Any = None


def resolve_llm_config(
    *,
    provider: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    temperature: float | int | None = None,
    max_tokens: int | None = None,
    timeout: float | int | None = None,
    context: Any = None,
) -> LLMConfig:
    """Resolve explicit node inputs, workflow secrets, and environment defaults."""
    normalized_provider = (provider or os.environ.get("BIONODULO_LLM_PROVIDER") or "openai").strip().lower()
    resolved_api_key = resolve_secret_value(
        api_key,
        context,
        "llm_api_key",
        default=_provider_api_key(normalized_provider),
    )

    resolved_api_base = (api_base or "").strip()
    if not resolved_api_base:
        resolved_api_base = os.environ.get("BIONODULO_LLM_BASE_URL", "")
    if normalized_provider == "litellm" and not resolved_api_base:
        resolved_api_base = os.environ.get("BIONODULO_LITELLM_BASE_URL", "http://localhost:4000/v1")

    return LLMConfig(
        provider=normalized_provider,
        model=_provider_model_str(normalized_provider, model),
        api_key=resolved_api_key,
        api_base=resolved_api_base,
        temperature=float(0.2 if temperature is None else temperature),
        max_tokens=int(1024 if max_tokens is None else max_tokens),
        timeout=float(60.0 if timeout is None else timeout),
    )


def _provider_api_key(provider: str) -> str:
    if provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY", "")
    if provider == "openrouter":
        return os.environ.get("OPENROUTER_API_KEY", "")
    if provider in {"custom", "litellm", "mock"}:
        return os.environ.get("LITELLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    return os.environ.get("OPENAI_API_KEY", "")


def _provider_model_str(provider: str, model: str | None) -> str:
    chosen = (model or "").strip()
    if provider == "anthropic":
        chosen = chosen or "claude-3-5-sonnet-20241022"
        return chosen if chosen.startswith("anthropic/") else f"anthropic/{chosen}"
    if provider == "openrouter":
        chosen = chosen or "openai/gpt-4.1-mini"
        return chosen if chosen.startswith("openrouter/") else f"openrouter/{chosen}"
    if provider == "openai":
        chosen = chosen or "gpt-4.1-mini"
        return chosen if chosen.startswith("openai/") else f"openai/{chosen}"
    return chosen or "gpt-4.1-mini"


async def call_llm(
    config: LLMConfig,
    messages: list[dict[str, str]],
    *,
    json_mode: bool = False,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> LLMResponse:
    """Call LiteLLM and normalize the response."""
    if not config.api_key and config.provider not in {"custom", "litellm", "mock"}:
        raise ValueError(f"{config.provider} API key is required.")
    try:
        import litellm
    except ImportError as exc:
        raise RuntimeError("LiteLLM is required for workflow AI nodes. Install with `pip install litellm`.") from exc

    kwargs: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": config.max_tokens,
        "timeout": config.timeout,
        "stream": False,
    }
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.api_key:
        kwargs["api_key"] = config.api_key
    if config.api_base:
        kwargs["api_base"] = config.api_base
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    attempts = max(1, int(max_retries or 1))
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await litellm.acompletion(**kwargs)
            break
        except Exception as exc:
            last_error = exc
            # Reasoning models reject `temperature` outright ("deprecated for
            # this model"). Which models do so is the vendor's business and
            # changes without notice, so react to the refusal instead of
            # maintaining a list that silently goes stale.
            if "temperature" in str(exc).lower() and "temperature" in kwargs:
                kwargs.pop("temperature")
                continue
            if attempt >= attempts - 1:
                return LLMResponse(
                    content="",
                    model=config.model,
                    error=f"LLM provider error after {attempts} attempts: {exc}",
                )
            if retry_delay > 0:
                await asyncio.sleep(float(retry_delay) * (2 ** attempt))
    else:
        return LLMResponse(
            content="",
            model=config.model,
            error=f"LLM provider error after {attempts} attempts: {last_error}",
        )

    choices = _obj_get(response, "choices", [])
    if not choices:
        return LLMResponse(content="", model=config.model, raw_response=response)
    choice = choices[0]
    message = _obj_get(choice, "message", {})
    content = _obj_get(message, "content", "") or ""
    if not str(content).strip():
        # LiteLLM implements JSON mode for providers that lack `response_format`
        # (Anthropic among them) by forcing a synthetic tool call, which leaves
        # `content` empty and the payload in the call's arguments. Reading it
        # back is what makes json_mode work on those providers at all -- without
        # this, every structured call looks like the model said nothing.
        for call in _obj_get(message, "tool_calls", []) or []:
            arguments = _obj_get(_obj_get(call, "function", {}), "arguments", "")
            if str(arguments).strip():
                content = arguments
                break
    usage = _obj_get(response, "usage", {}) or {}
    if not isinstance(usage, dict):
        usage = dict(usage) if hasattr(usage, "items") else {}
    return LLMResponse(
        content=str(content),
        model=str(_obj_get(response, "model", config.model) or config.model),
        usage=usage,
        finish_reason=str(_obj_get(choice, "finish_reason", "") or ""),
        raw_response=response,
    )


def render_prompt(template: str, variables: dict[str, Any] | None = None) -> str:
    """Render {{ variable }} placeholders using a simple safe substitution."""
    values = variables or {}

    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in values:
            return match.group(0)
        return _stringify_prompt_value(values[key])

    return re.sub(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}", replace, str(template))


def safe_json_parse(text: str) -> dict[str, Any]:
    """Parse JSON objects from plain or fenced LLM output."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Reasoning models often narrate around the JSON even when told not to,
        # and `response_format` is not honoured by every provider. Recover the
        # outermost object rather than discarding a good answer.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _stringify_prompt_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(_stringify_prompt_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def _obj_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

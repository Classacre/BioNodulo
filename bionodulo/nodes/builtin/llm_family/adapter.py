"""Validated LiteLLM boundary shared by provider-backed workflow nodes.

Authority is LiteLLM 1.87.1 at commit
cc9b99c2e35795476c7a00e34a85ee0573d6d66c. Provider-specific model names
remain caller supplied because the upstream model catalog changes independently.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bionodulo.ai.llm_backend import (
    LLMConfig,
    LLMResponse,
    call_llm as _backend_call_llm,
    render_prompt,
    resolve_llm_config,
)
from bionodulo.nodes.base import BaseNode


LITELLM_VERSION = "1.87.1"
LITELLM_SOURCE_URL = "https://github.com/BerriAI/litellm"
LITELLM_SOURCE_COMMIT = "cc9b99c2e35795476c7a00e34a85ee0573d6d66c"
LITELLM_DOCUMENTATION_URL = "https://docs.litellm.ai/docs/completion/input"
SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic", "openrouter", "litellm", "custom"})


class LiteLLMNode(BaseNode):
    """Shared pinned authority metadata for provider-backed nodes."""

    NODE_ID = ""
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    VERSION = LITELLM_VERSION
    DOCUMENTATION_URL = LITELLM_DOCUMENTATION_URL
    GIT_URL = LITELLM_SOURCE_URL
    GIT_COMMIT = LITELLM_SOURCE_COMMIT
    CITATION_URLS = [LITELLM_DOCUMENTATION_URL, LITELLM_SOURCE_URL]
    ENVIRONMENT = {"package_constraints": {"litellm": LITELLM_VERSION}}


def _parse_json_object(value: Any, field_name: str) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _llm_config_from_kwargs(kwargs: dict[str, Any]) -> LLMConfig:
    config = resolve_llm_config(
        provider=kwargs.get("provider"),
        model=kwargs.get("model"),
        api_key=kwargs.get("api_key"),
        api_base=kwargs.get("api_base"),
        temperature=kwargs.get("temperature"),
        max_tokens=kwargs.get("max_tokens"),
        timeout=kwargs.get("timeout"),
        context=kwargs.get("context"),
    )
    _validate_llm_config(config)
    return config


def _validate_llm_config(config: LLMConfig) -> None:
    if config.provider not in SUPPORTED_PROVIDERS:
        allowed = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported LLM provider {config.provider!r}; expected one of: {allowed}")
    if not str(config.model or "").strip():
        raise ValueError("LLM model must be non-empty")
    if config.provider == "custom":
        if not config.api_base:
            raise ValueError("custom LLM provider requires api_base")
        parsed = urlparse(config.api_base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("custom LLM api_base must be an absolute HTTP(S) URL")

    expected_prefix = {
        "openai": "openai/",
        "anthropic": "anthropic/",
        "openrouter": "openrouter/",
    }.get(config.provider)
    if expected_prefix and not config.model.startswith(expected_prefix):
        raise ValueError(f"Resolved {config.provider} model must start with {expected_prefix!r}")


async def call_llm(
    config: LLMConfig,
    messages: list[dict[str, Any]],
    *,
    json_mode: bool = False,
) -> LLMResponse:
    """Call the shared backend and turn provider failures into fatal node errors."""
    response = await _backend_call_llm(config, messages, json_mode=json_mode)
    if response.error:
        raise RuntimeError(response.error)
    if not str(response.content or "").strip():
        raise RuntimeError("LLM provider returned an empty completion")
    if json_mode:
        safe_json_parse(response.content)
    return response


def safe_json_parse(text: str) -> dict[str, Any]:
    """Parse exactly one JSON object, including an optional Markdown fence."""
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("LLM provider returned malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM provider JSON response must be an object")
    return parsed


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = base / node.NODE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _messages(*, prompt: str, system_prompt: str = "") -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": prompt})
    return messages


def validate_choice(value: Any, field_name: str, choices: tuple[str, ...] | list[str]) -> str:
    normalized = str(value or "").strip()
    if normalized not in choices:
        allowed = ", ".join(choices)
        raise ValueError(f"{field_name} must be one of: {allowed}")
    return normalized


def require_artifacts(*paths: Path) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Expected node artifacts were not created: {', '.join(missing)}")


__all__ = [
    "LITELLM_DOCUMENTATION_URL",
    "LITELLM_SOURCE_COMMIT",
    "LITELLM_SOURCE_URL",
    "LITELLM_VERSION",
    "LiteLLMNode",
    "_llm_config_from_kwargs",
    "_messages",
    "_node_output_dir",
    "_parse_json_object",
    "call_llm",
    "render_prompt",
    "require_artifacts",
    "safe_json_parse",
    "validate_choice",
]

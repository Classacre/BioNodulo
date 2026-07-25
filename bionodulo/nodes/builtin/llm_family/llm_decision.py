"""Validated structured LLM decisions."""

from __future__ import annotations

from typing import Any

from .adapter import LiteLLMNode, _llm_config_from_kwargs, _messages, call_llm, safe_json_parse


class LLMDecisionNode(LiteLLMNode):
    """Use an LLM to classify input into configured labels."""

    NODE_ID = "llm_decision"
    DISPLAY_NAME = "LLM Decision"
    CATEGORY = "ai"
    DESCRIPTION = "Use an LLM to classify input data and return a workflow decision label"
    SEARCH_ALIASES = ["llm", "ai", "decision", "classify", "route", "branch", "condition"]
    RETURN_TYPES = ("STRING", "BOOLEAN", "JSON")
    RETURN_NAMES = ("label", "matched", "decision_json")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_data": ("STRING", {"default": "", "multiline": True, "description": "Data to analyze"}),
                "criteria": ("STRING", {"default": "", "multiline": True, "description": "Decision criteria"}),
                "labels": ("STRING", {"default": "pass, fail", "description": "Comma-separated allowed labels"}),
            },
            "optional": {
                "default_label": (
                    "STRING",
                    {"default": "fail", "description": "Fallback label when output is invalid"},
                ),
                "system_prompt": (
                    "STRING",
                    {"default": "", "multiline": True, "description": "Optional system prompt"},
                ),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 256, "min": 1, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, bool, dict[str, Any]]:
        labels = _parse_labels(kwargs.get("labels"))
        default_label = str(kwargs.get("default_label", "") or labels[-1]).strip().lower()
        if default_label not in labels:
            raise ValueError("default_label must be one of labels")

        prompt = (
            f"{kwargs.get('criteria', '')}\n\n"
            f"Allowed labels: {', '.join(labels)}\n"
            "Return a JSON object with keys label, confidence, and reason.\n\n"
            f"Input data:\n{kwargs.get('input_data', '')}"
        )
        system_prompt = str(kwargs.get("system_prompt", "") or "You are a strict workflow classifier.")
        config = _llm_config_from_kwargs(kwargs)
        response = await call_llm(config, _messages(prompt=prompt, system_prompt=system_prompt), json_mode=True)
        parsed = safe_json_parse(response.content)
        raw_label = str(parsed.get("label", "")).strip().lower()
        if raw_label in labels:
            parsed.setdefault("matched", True)
            parsed["label"] = raw_label
            return (raw_label, True, parsed)

        reason = parsed.get("reason", response.content)
        return (
            default_label,
            False,
            {"label": default_label, "matched": False, "raw_label": raw_label, "reason": reason},
        )


def _parse_labels(value: Any) -> list[str]:
    labels = [label.strip().lower() for label in str(value or "").split(",") if label.strip()]
    if not labels:
        raise ValueError("labels must include at least one label")
    return labels

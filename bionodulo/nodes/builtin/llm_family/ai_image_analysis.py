"""Validated provider-backed multimodal image analysis."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _node_output_dir,
    call_llm,
    require_artifacts,
    safe_json_parse,
    validate_choice,
)


class AIImageAnalysisNode(LiteLLMNode):
    """Analyze scientific images with a vision-capable LLM."""

    NODE_ID = "ai_image_analysis"
    DISPLAY_NAME = "AI Image Analysis"
    CATEGORY = "ai"
    DESCRIPTION = (
        "Analyze bioinformatics images such as gels, microscopy, karyograms, plots, and colony plates "
        "using multimodal LLMs."
    )
    SEARCH_ALIASES = [
        "image",
        "vision",
        "gel",
        "microscopy",
        "karyotype",
        "karyogram",
        "plot",
        "analyze",
        "multimodal",
        "colony",
        "western",
    ]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("analysis_json", "description_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_image": ("IMAGE", {"description": "Image file to analyze"}),
                "analysis_task": (
                    "STRING",
                    {
                        "default": "general",
                        "options": [
                            "general",
                            "gel_electrophoresis",
                            "microscopy",
                            "karyogram",
                            "plot",
                            "western_blot",
                            "colony_counting",
                            "custom",
                        ],
                    },
                ),
            },
            "optional": {
                "custom_prompt": ("STRING", {"default": "", "multiline": True}),
                "expected_ladder": ("STRING", {"default": "", "description": "Gel ladder sizes, comma-separated"}),
                "scale_bar": ("STRING", {"default": "", "description": "Microscopy scale bar, e.g. 20um"}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Vision model override"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
                "json_mode": ("BOOLEAN", {"default": True}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "analysis.json"

        image_path = Path(str(kwargs.get("input_image", "") or ""))
        analysis_task = validate_choice(
            kwargs.get("analysis_task", "general"),
            "analysis_task",
            (*_IMAGE_ANALYSIS_PROMPTS, "custom"),
        )
        if not image_path.exists():
            raise FileNotFoundError(f"AI image input not found: {image_path}")
        if image_path.suffix.lower() not in _IMAGE_MIME_BY_SUFFIX:
            raise ValueError(f"Unsupported image format: {image_path.suffix or '<none>'}")

        mime_type = _image_mime_type(image_path)
        image_bytes = image_path.read_bytes()
        if not image_bytes:
            raise ValueError("AI image input must not be empty")
        prompt = _image_analysis_prompt(
            analysis_task=analysis_task,
            custom_prompt=str(kwargs.get("custom_prompt", "") or ""),
            expected_ladder=str(kwargs.get("expected_ladder", "") or ""),
            scale_bar=str(kwargs.get("scale_bar", "") or ""),
        )
        config = _llm_config_from_kwargs(
            {
                **kwargs,
                "context": context,
                "model": _vision_model_override(str(kwargs.get("provider", "openai") or "openai"), kwargs.get("model")),
            }
        )
        json_mode = bool(kwargs.get("json_mode", True))
        messages = _image_analysis_messages(prompt=prompt, image_bytes=image_bytes, mime_type=mime_type)
        response = await call_llm(config, messages, json_mode=json_mode)
        parsed = safe_json_parse(response.content) if json_mode else {}
        description = str(parsed.get("description") or parsed.get("summary") or response.content)
        analysis = parsed or {"description": response.content}
        payload = {
            "input_image": str(image_path),
            "analysis_task": analysis_task,
            "mime_type": mime_type,
            "image_size_bytes": len(image_bytes),
            "model": response.model or config.model,
            "usage": response.usage,
            "analysis": analysis,
            "description": description,
        }
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        require_artifacts(json_path)
        return {"outputs": {"analysis_json": str(json_path), "description_text": description}}


_IMAGE_ANALYSIS_PROMPTS = {
    "general": (
        "Describe this scientific image in detail. Identify the image type, visible labels, key features, "
        "and cautious interpretation of the findings."
    ),
    "gel_electrophoresis": (
        "Analyze this gel electrophoresis image. Estimate lane count, band positions, ladder relationship, "
        "smearing or artifacts, and lane-by-lane observations. Return structured JSON when possible."
    ),
    "microscopy": (
        "Analyze this microscopy image. Estimate cell count or density, morphology, staining patterns, "
        "notable abnormalities, and limitations. Return structured JSON when possible."
    ),
    "karyogram": (
        "Analyze this karyogram. Estimate chromosome count, visible abnormalities, sex chromosome pattern, "
        "and uncertainty. Return structured JSON when possible."
    ),
    "plot": (
        "Analyze this scientific plot. Identify plot type, axes, trends, outliers, labels, and limitations. "
        "Return structured JSON when possible."
    ),
    "western_blot": (
        "Analyze this Western blot. Estimate lane count, band positions, relative intensity, artifacts, "
        "and lane-by-lane observations. Return structured JSON when possible."
    ),
    "colony_counting": (
        "Analyze this colony plate image. Estimate colony count, size distribution, morphology, density, "
        "and uncertainty. Return structured JSON when possible."
    ),
}


_VISION_MODEL_BY_PROVIDER = {
    "anthropic": "claude-3-5-sonnet-20241022",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
    "litellm": "gpt-4o",
    "custom": "gpt-4o",
}


_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
}


def _vision_model_override(provider: str, model: Any) -> str:
    value = str(model or "").strip()
    if value:
        return value
    return _VISION_MODEL_BY_PROVIDER.get(str(provider or "openai").strip().lower(), "gpt-4o")


def _image_analysis_prompt(
    *,
    analysis_task: str,
    custom_prompt: str,
    expected_ladder: str,
    scale_bar: str,
) -> str:
    task = str(analysis_task or "general")
    prompt = str(custom_prompt or "").strip() if task == "custom" else ""
    if not prompt:
        prompt = _IMAGE_ANALYSIS_PROMPTS.get(task, _IMAGE_ANALYSIS_PROMPTS["general"])
    context_lines = []
    if expected_ladder.strip():
        context_lines.append(f"Expected ladder sizes: {expected_ladder.strip()}")
    if scale_bar.strip():
        context_lines.append(f"Scale bar: {scale_bar.strip()}")
    if context_lines:
        prompt = f"{prompt}\n\nAdditional context:\n" + "\n".join(context_lines)
    return prompt


def _image_analysis_messages(prompt: str, image_bytes: bytes, mime_type: str) -> list[dict[str, Any]]:
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    return [
        {
            "role": "system",
            "content": (
                "You are an expert scientific image analysis assistant. Provide cautious, structured findings and "
                "call out uncertainty instead of overclaiming."
            ),
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]


def _image_mime_type(path: Path) -> str:
    return _IMAGE_MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")

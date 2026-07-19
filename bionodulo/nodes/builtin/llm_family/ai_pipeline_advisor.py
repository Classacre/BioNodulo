"""Structured LLM pipeline recommendations."""

from __future__ import annotations

import json
from typing import Any

from .adapter import (
    LiteLLMNode,
    _llm_config_from_kwargs,
    _messages,
    _node_output_dir,
    _parse_json_object,
    call_llm,
    require_artifacts,
    safe_json_parse,
    validate_choice,
)


class AIPipelineAdvisorNode(LiteLLMNode):
    """Recommend bioinformatics workflow structure and parameters with an LLM."""

    NODE_ID = "ai_pipeline_advisor"
    DISPLAY_NAME = "AI Pipeline Advisor"
    CATEGORY = "ai"
    DESCRIPTION = "Recommend bioinformatics pipeline nodes and parameters from experiment metadata."
    SEARCH_ALIASES = ["pipeline", "advisor", "recommend", "parameters", "workflow", "planning", "metadata"]
    RETURN_TYPES = ("JSON", "STRING")
    RETURN_NAMES = ("recommendations_json", "rationale_text")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["litellm"]
    EXPERIMENTAL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "experiment_type": ("STRING", {"default": "bulk_rnaseq", "description": "Experiment or assay type"}),
                "metadata": (
                    "JSON",
                    {"default": "{}", "multiline": True, "description": "Experimental metadata as JSON"},
                ),
            },
            "optional": {
                "analysis_goal": ("STRING", {"default": "", "multiline": True}),
                "available_inputs": ("STRING", {"default": "", "multiline": True}),
                "constraints": ("STRING", {"default": "", "multiline": True}),
                "output_format": ("STRING", {"default": "both", "options": ["json", "rationale", "both"]}),
                "provider": (["openai", "anthropic", "openrouter", "litellm", "custom"], {"default": "openai"}),
                "model": ("STRING", {"default": "", "description": "Provider model name"}),
                "api_key": ("STRING", {"default": "", "password": True, "description": "Optional API key override"}),
                "api_base": ("STRING", {"default": "", "description": "Optional compatible API base URL"}),
                "temperature": ("FLOAT", {"default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05}),
                "max_tokens": ("INT", {"default": 4096, "min": 256, "max": 128000, "step": 1}),
                "timeout": ("FLOAT", {"default": 60.0, "min": 1.0, "max": 600.0, "step": 1.0}),
            },
            "hidden": {
                "context": ("CONTEXT", {}),
            },
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        out_dir = _node_output_dir(self, context)
        json_path = out_dir / "recommendations.json"
        rationale_path = out_dir / "rationale.txt"

        experiment_type = str(kwargs.get("experiment_type", "") or "").strip()
        if not experiment_type:
            raise ValueError("AI Pipeline Advisor requires an experiment_type")
        metadata = _parse_json_object(kwargs.get("metadata"), "metadata")
        analysis_goal = str(kwargs.get("analysis_goal", "") or "").strip()
        available_inputs = str(kwargs.get("available_inputs", "") or "").strip()
        constraints = str(kwargs.get("constraints", "") or "").strip()
        output_format = validate_choice(
            kwargs.get("output_format", "both"), "output_format", ("json", "rationale", "both")
        )

        config = _llm_config_from_kwargs({**kwargs, "context": context})
        response = await call_llm(
            config,
            _messages(
                system_prompt=(
                    "You are a senior bioinformatics workflow architect. Recommend practical BioNodulo "
                    "pipeline steps, parameters, quality controls, and risks from the supplied metadata."
                ),
                prompt=_pipeline_advisor_prompt(
                    experiment_type=experiment_type,
                    metadata=metadata,
                    analysis_goal=analysis_goal,
                    available_inputs=available_inputs,
                    constraints=constraints,
                ),
            ),
            json_mode=True,
        )
        recommendations = safe_json_parse(response.content) or {"raw_recommendations": response.content}
        rationale = _pipeline_advisor_rationale(recommendations, response.content)
        payload = {
            "experiment_type": experiment_type,
            "metadata": metadata,
            "analysis_goal": analysis_goal,
            "available_inputs": available_inputs,
            "constraints": constraints,
            "recommendations": recommendations,
            "rationale": rationale,
            "usage": response.usage,
            "model": response.model or config.model,
        }

        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        rationale_path.write_text(rationale, encoding="utf-8")
        require_artifacts(json_path, rationale_path)
        return {
            "outputs": {
                "recommendations_json": str(json_path) if output_format in {"json", "both"} else "",
                "rationale_text": str(rationale_path) if output_format in {"rationale", "both"} else "",
            }
        }


def _pipeline_advisor_prompt(
    *,
    experiment_type: str,
    metadata: dict[str, Any],
    analysis_goal: str,
    available_inputs: str,
    constraints: str,
) -> str:
    sections = [
        f"Experiment type: {experiment_type}",
        f"Metadata:\n{json.dumps(metadata, indent=2, sort_keys=True)}",
    ]
    if analysis_goal:
        sections.append(f"Analysis goal: {analysis_goal}")
    if available_inputs:
        sections.append(f"Available inputs: {available_inputs}")
    if constraints:
        sections.append(f"Constraints: {constraints}")
    sections.append(
        "Return a JSON object with keys recommended_pipeline, recommended_nodes, "
        "parameter_recommendations, quality_controls, warnings, and rationale. "
        "recommended_nodes should be an ordered array of objects with node_id, reason, and optional parameters."
    )
    return "\n\n".join(sections)


def _pipeline_advisor_rationale(recommendations: dict[str, Any], raw_content: str) -> str:
    rationale = recommendations.get("rationale") if isinstance(recommendations, dict) else ""
    if isinstance(rationale, list):
        return "\n".join(str(item) for item in rationale if str(item).strip())
    if str(rationale or "").strip():
        return str(rationale).strip()
    return str(raw_content or "").strip()

"""Compute the documented ODGI summary and adapt it to stable JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .odgi_adapter import (
    ODGICommandNode,
    bash_pipeline,
    stats_argv,
    stats_json_pipeline,
    validate_input_file,
    validate_positive_int,
)


class ODGIStatsNode(ODGICommandNode):
    """Run ``odgi stats -S`` on GFA or ODGI input."""

    NODE_ID = "odgi_stats"
    DISPLAY_NAME = "ODGI Stats"
    DESCRIPTION = "Compute ODGI graph dimensions and expose them as deterministic JSON"
    SEARCH_ALIASES = ["odgi", "odgi stats", "graph statistics", "pangenome graph", "stats json"]
    RETURN_TYPES = ("JSON",)
    RETURN_NAMES = ("stats_json",)
    UPSTREAM_SOURCE = "src/subcommand/stats_main.cpp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gfa_graph": ("GFA", {"description": "Readable GFAv1 graph; ODGI accepts GFA on the fly"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "stats.json"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        error = validate_input_file(inputs.get("gfa_graph"), "gfa_graph")
        if error:
            return error
        error = validate_positive_int(inputs.get("threads", 1), "threads")
        if error:
            return error
        return True

    @classmethod
    def stats_argv(cls, inputs: dict[str, Any]) -> list[str]:
        return stats_argv(str(inputs.get("gfa_graph", "")), int(inputs.get("threads", 1)))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "stats.json"
        return bash_pipeline(
            [
                stats_json_pipeline(
                    str(inputs.get("gfa_graph", "")),
                    output,
                    int(inputs.get("threads", 1)),
                )
            ]
        )

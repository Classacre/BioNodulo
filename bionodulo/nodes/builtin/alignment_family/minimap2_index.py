"""Build one Minimap2 .mmi index file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .minimap2_adapter import MINIMAP2_PRESETS, Minimap2CommandNode, path_value


class Minimap2IndexNode(Minimap2CommandNode):
    NODE_ID = "minimap2_index"
    DISPLAY_NAME = "Minimap2 Index"
    DESCRIPTION = "Build a Minimap2 index file from one reference FASTA"
    SEARCH_ALIASES = ["minimap2", "index", "long reads", "mmi"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("index",)
    UPSTREAM_SOURCE = "index.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"reference": ("FASTA", {"description": "Reference FASTA"})},
            "optional": {
                "preset": (
                    "STRING",
                    {"default": "map-ont", "options": list(MINIMAP2_PRESETS)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "reference.mmi"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if path_value(inputs.get("reference")) is None:
            return "reference must be a non-empty path-like value"
        return cls.validate_preset(inputs, "map-ont")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "minimap2",
            "-x",
            str(inputs.get("preset", "map-ont")),
            "-d",
            str(output / "reference.mmi"),
            str(inputs.get("reference", "")),
        ]


__all__ = ["Minimap2IndexNode"]

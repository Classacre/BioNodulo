"""Align one read file with Minimap2 and capture SAM stdout."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .minimap2_adapter import MINIMAP2_PRESETS, Minimap2CommandNode, path_value


class Minimap2AlignNode(Minimap2CommandNode):
    NODE_ID = "minimap2_align"
    DISPLAY_NAME = "Minimap2 Align"
    DESCRIPTION = "Align nucleotide reads to a FASTA reference or Minimap2 .mmi index"
    SEARCH_ALIASES = ["minimap2", "align", "long read", "pacbio", "ont"]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("alignment",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_SOURCE = "main.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "One FASTQ/FASTA read file"}),
                "reference": ("FILE", {"description": "Reference FASTA or Minimap2 .mmi index"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "preset": ("STRING", {"default": "sr", "options": list(MINIMAP2_PRESETS)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "alignment.sam"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("reads", "reference"):
            if path_value(inputs.get(key)) is None:
                return f"{key} must be a non-empty path-like value"
        validation = cls.validate_threads(inputs)
        if validation is not True:
            return validation
        return cls.validate_preset(inputs, "sr")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "minimap2",
            "-a",
            "-x",
            str(inputs.get("preset", "sr")),
            "-t",
            str(inputs.get("threads", 8)),
            str(inputs.get("reference", "")),
            str(inputs.get("reads", "")),
        ]


__all__ = ["Minimap2AlignNode"]

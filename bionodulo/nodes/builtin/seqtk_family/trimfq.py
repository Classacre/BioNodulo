"""Seqtk 1.4 ``trimfq`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKTrimFQNode(SeqtkStdoutNode):
    """Trim FASTA/Q records by Mott quality or fixed end lengths."""

    NODE_ID = "seqtk_trimfq"
    DISPLAY_NAME = "SeqTK Trim FASTQ"
    CATEGORY = "trimming"
    DESCRIPTION = "Trim FASTA/Q records using Mott quality trimming or fixed left/right/maximum lengths."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "trimfq", "Mott trimming", "FASTQ trimming"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("trimmed_records",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_trimfq"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {
                "l": ("INT", {"default": 30, "min": 0, "description": "Minimum retained length for quality trimming"}),
                "q": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "description": "Error-rate threshold"}),
                "b": ("INT", {"default": 0, "min": 0, "description": "Trim bases from the left"}),
                "e": ("INT", {"default": 0, "min": 0, "description": "Trim bases from the right"}),
                "L": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Retain at most this many bases from the 5-prime end"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"trimmed{cls.sequence_extension(inputs.get('in_file'))}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("input_ext", "mode_select"))
        if validation is not True:
            return validation
        validation = cls.validate_number(inputs.get("q", 0.05), "q", minimum=0.0, maximum=1.0)
        if validation is not True:
            return validation
        for key, default in (("l", 30), ("b", 0), ("e", 0), ("L", 0)):
            validation = cls.validate_int(inputs.get(key, default), key, minimum=0)
            if validation is not True:
                return validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "seqtk",
            "trimfq",
            "-l",
            str(inputs.get("l", 30)),
            "-q",
            str(inputs.get("q", 0.05)),
            "-b",
            str(inputs.get("b", 0)),
            "-e",
            str(inputs.get("e", 0)),
            "-L",
            str(inputs.get("L", 0)),
            cls.path_value(inputs["in_file"]),
        )

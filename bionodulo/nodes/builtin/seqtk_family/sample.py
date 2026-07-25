"""Seqtk 1.4 ``sample`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKSampleNode(SeqtkStdoutNode):
    """Subsample records by fraction or approximate record count."""

    NODE_ID = "seqtk_sample"
    DISPLAY_NAME = "SeqTK Sample"
    DESCRIPTION = "Subsample FASTA/Q records using Seqtk's fraction-or-count positional argument."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "sample", "subsample reads"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("subsampled_records",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_sample"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
                "subsample_size": (
                    "FLOAT",
                    {"description": "Fraction below 1, or approximate record count at least 1"},
                ),
            },
            "optional": {
                "two_pass": (
                    "BOOLEAN",
                    {"default": False, "description": "Use reduced-memory two-pass count sampling"},
                ),
                "s": ("INT", {"default": 11, "description": "Random-number seed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"subsampled{cls.sequence_extension(inputs.get('in_file'))}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.reject_legacy(inputs, ("input_ext", "single_pass_mode"))
        if validation is not True:
            return validation
        validation = cls.validate_number(inputs.get("subsample_size"), "subsample_size")
        if validation is not True:
            return validation
        return cls.validate_int(inputs.get("s", 11), "s")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "seqtk", "sample")
        if inputs.get("two_pass"):
            command.append("-2")
        command.extend(
            [
                "-s",
                str(inputs.get("s", 11)),
                cls.path_value(inputs["in_file"]),
                str(inputs["subsample_size"]),
            ]
        )
        return command

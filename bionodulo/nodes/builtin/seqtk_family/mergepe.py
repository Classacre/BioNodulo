"""Seqtk 1.4 ``mergepe`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKMergePENode(SeqtkStdoutNode):
    """Interleave records from two paired FASTA/Q inputs."""

    NODE_ID = "seqtk_mergepe"
    DISPLAY_NAME = "SeqTK Merge Paired-End"
    DESCRIPTION = "Interleave two paired FASTA/Q files in first-read, second-read order."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "mergepe", "interleave paired reads"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("interleaved_pairs",)
    REQUIRED_PATH_INPUTS = ("in_fq1", "in_fq2")
    UPSTREAM_FUNCTION = "stk_mergepe"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fq1": (("FASTA", "FASTQ"), {"description": "First paired FASTA/Q input"}),
                "in_fq2": (("FASTA", "FASTQ"), {"description": "Second paired FASTA/Q input"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"interleaved{cls.sequence_extension(inputs.get('in_fq1'))}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.reject_legacy(inputs, ("input_ext",))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "seqtk",
            "mergepe",
            cls.path_value(inputs["in_fq1"]),
            cls.path_value(inputs["in_fq2"]),
        )

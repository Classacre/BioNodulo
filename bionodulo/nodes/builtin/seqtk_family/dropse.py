"""Seqtk 1.4 ``dropse`` node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKDropSENode(SeqtkStdoutNode):
    """Drop unpaired records from an interleaved FASTA/Q stream."""

    NODE_ID = "seqtk_dropse"
    DISPLAY_NAME = "SeqTK DropSE"
    DESCRIPTION = "Keep only adjacent records whose names form an interleaved pair."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "dropse", "remove unpaired reads"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("paired_records",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_dropse"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Interleaved FASTA/Q input"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"paired{cls.sequence_extension(inputs.get('in_file'))}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.reject_legacy(inputs, ("input_ext",))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "seqtk", "dropse", cls.path_value(inputs["in_file"]))

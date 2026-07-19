"""Seqtk 1.4 ``comp`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKCompNode(SeqtkStdoutNode):
    """Report native per-record nucleotide-composition columns."""

    NODE_ID = "seqtk_comp"
    DISPLAY_NAME = "SeqTK Composition"
    DESCRIPTION = "Report native Seqtk nucleotide composition for FASTA/FASTQ records or BED regions."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "comp", "nucleotide composition"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("composition",)
    OUTPUT_FILENAMES = ("composition.tsv",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_comp"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {
                "u": ("BOOLEAN", {"default": False, "description": "Count uppercase bases only"}),
                "in_bed": ("BED", {"default": "", "description": "Restrict composition to BED regions"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("in_bed"):
            return cls.require_path(inputs, "in_bed")
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = cls.checked_command(inputs, "seqtk", "comp")
        if inputs.get("u"):
            command.append("-u")
        cls.add_value(command, "-r", inputs.get("in_bed"))
        command.append(cls.path_value(inputs["in_file"]))
        return command

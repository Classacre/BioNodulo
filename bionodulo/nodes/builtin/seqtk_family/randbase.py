"""Seqtk 1.4 ``randbase`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKRandBaseNode(SeqtkStdoutNode):
    """Resolve two-base ambiguity codes to one random allele."""

    NODE_ID = "seqtk_randbase"
    DISPLAY_NAME = "SeqTK Random Base"
    DESCRIPTION = "Randomly choose one allele for each two-base IUPAC ambiguity and emit FASTA."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "randbase", "resolve IUPAC"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("unambiguous_fasta",)
    OUTPUT_FILENAMES = ("unambiguous.fasta",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_randbase"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q sequence file"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.reject_legacy(inputs, ("input_ext",))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "seqtk", "randbase", cls.path_value(inputs["in_file"]))

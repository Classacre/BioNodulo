"""Seqtk 1.4 ``mutfa`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKMutFANode(SeqtkStdoutNode):
    """Apply point mutations from Seqtk's four-column SNP format."""

    NODE_ID = "seqtk_mutfa"
    DISPLAY_NAME = "SeqTK Mutate FASTA"
    DESCRIPTION = "Apply one-base substitutions from a four-column, 1-based SNP table."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "mutfa", "point mutation", "SNP table"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("mutated_fasta",)
    OUTPUT_FILENAMES = ("mutated.fasta",)
    REQUIRED_PATH_INPUTS = ("in_file", "in_snp")
    UPSTREAM_FUNCTION = "stk_mutfa"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q sequence file"}),
                "in_snp": (
                    "TSV",
                    {"description": "At least four columns: name, 1-based position, placeholder, replacement base"},
                ),
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
        return cls.checked_command(
            inputs,
            "seqtk",
            "mutfa",
            cls.path_value(inputs["in_file"]),
            cls.path_value(inputs["in_snp"]),
        )

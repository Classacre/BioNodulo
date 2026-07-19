"""Seqtk 1.4 ``listhet`` node."""

from __future__ import annotations

from typing import Any

from .adapter import SeqtkStdoutNode


class SeqTKListHetNode(SeqtkStdoutNode):
    """List positions containing two-base IUPAC ambiguity codes."""

    NODE_ID = "seqtk_listhet"
    DISPLAY_NAME = "SeqTK List Heterozygous Bases"
    DESCRIPTION = "List each two-base IUPAC ambiguity position using Seqtk's native columns."
    SEARCH_ALIASES = ["BioNodulo builtin", "Seqtk", "listhet", "IUPAC", "heterozygous positions"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("heterozygous_bases",)
    OUTPUT_FILENAMES = ("heterozygous_bases.tsv",)
    REQUIRED_PATH_INPUTS = ("in_file",)
    UPSTREAM_FUNCTION = "stk_listhet"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": (("FASTA", "FASTQ"), {"description": "Input FASTA/Q, optionally gzip-compressed"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "seqtk", "listhet", cls.path_value(inputs["in_file"]))

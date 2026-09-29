"""EMBOSS revseq owner: reverse and complement a nucleotide sequence."""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossRevseqNode(EmbossBase):
    """Reverse-complement (or reverse/complement independently) a nucleotide sequence."""

    NODE_ID = "emboss_revseq"
    DISPLAY_NAME = "EMBOSS Revseq"
    CATEGORY = "emboss"
    DESCRIPTION = "Reverse and complement a nucleotide sequence (reverse complement by default)"
    SEARCH_ALIASES = ["emboss", "revseq", "reverse complement", "revcomp", "complement", "reverse"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("reverse_complement",)
    OUTPUT_FILENAMES = ("reverse_complement.fasta",)
    REQUIRED_EXECUTABLES = ["revseq"]
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/revseq.html"
    UPSTREAM_MANPAGE = "doc/manuals/emboss_doc/revseq.html"
    UPSTREAM_SOURCE = "emboss/emboss/revseq.c"
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": "https://bio.tools/revseq",
        "topics": [{"uri": "http://edamontology.org/topic_3071", "label": "Biological databases"}],
        "operations": [
            {"uri": "http://edamontology.org/operation_0363", "label": "Reverse complement"}
        ],
        "citation_evidence": [
            {
                "identifier": "10.1016/S0168-9525(00)02024-2",
                "source_url": "https://bio.tools/revseq",
                "checked_at": "2026-09-25",
                "note": (
                    "The bio.tools 'revseq' record lists the EMBOSS Trends in Genetics 2000 "
                    "software paper. This is the suite citation, not a version-specific DOI."
                ),
            }
        ],
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sequence": (
                    ("FASTA", "FILE"),
                    {"description": "Input nucleotide sequence file (FASTA)"},
                ),
            },
            "optional": {
                "reverse": (
                    "BOOLEAN",
                    {"default": True, "description": "Reverse the sequence order (EMBOSS default: yes)"},
                ),
                "complement": (
                    "BOOLEAN",
                    {"default": True, "description": "Complement each base (EMBOSS default: yes)"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "revseq",
            "-sequence",
            str(inputs.get("sequence", "")),
            "-outseq",
            str(cls.outseq_path(inputs)),
        ]
        # revseq's own defaults are reverse=yes and complement=yes, so only the
        # negating qualifiers need to be rendered.
        if inputs.get("reverse") is False:
            command.append("-noreverse")
        if inputs.get("complement") is False:
            command.append("-nocomplement")
        return command

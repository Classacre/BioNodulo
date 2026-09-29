"""EMBOSS transeq owner: translate a nucleotide CDS to protein."""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase

# EMBOSS transeq -frame accepts the three forward frames, the three reverse
# frames, and 6 for all six.  Reject anything else before it reaches the tool.
TRANSEQ_FRAMES = ("1", "2", "3", "-1", "-2", "-3", "6")


class EmbossTranseqNode(EmbossBase):
    """Translate a nucleotide sequence in one or all six reading frames."""

    NODE_ID = "emboss_transeq"
    DISPLAY_NAME = "EMBOSS Transeq"
    CATEGORY = "emboss"
    DESCRIPTION = "Translate a nucleotide CDS into a protein sequence in a chosen reading frame"
    SEARCH_ALIASES = ["emboss", "transeq", "translate", "translation", "cds", "protein", "six frame"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("protein",)
    OUTPUT_FILENAMES = ("translated.fasta",)
    REQUIRED_EXECUTABLES = ["transeq"]
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/transeq.html"
    UPSTREAM_MANPAGE = "doc/manuals/emboss_doc/transeq.html"
    UPSTREAM_SOURCE = "emboss/emboss/transeq.c"
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": "https://bio.tools/transeq",
        "topics": [{"uri": "http://edamontology.org/topic_0203", "label": "Gene expression"}],
        "operations": [{"uri": "http://edamontology.org/operation_0371", "label": "DNA translation"}],
        "citation_evidence": [
            {
                "identifier": "10.1016/S0168-9525(00)02024-2",
                "source_url": "https://bio.tools/transeq",
                "checked_at": "2026-09-25",
                "note": (
                    "The bio.tools 'transeq' record lists the EMBOSS Trends in Genetics 2000 "
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
                "frame": (
                    "STRING",
                    {
                        "default": "1",
                        "options": list(TRANSEQ_FRAMES),
                        "description": "Reading frame: 1/2/3 forward, -1/-2/-3 reverse, 6 for all six",
                    },
                ),
                "table": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 23,
                        "description": "EMBOSS/NCBI genetic code table number (0 = Standard)",
                    },
                ),
                "trim": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove trailing stop codons from the translation"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "transeq",
            "-sequence",
            str(inputs.get("sequence", "")),
            "-outseq",
            str(cls.outseq_path(inputs)),
        ]
        frame = str(inputs.get("frame", "1") or "1")
        if frame != "1":
            command.extend(["-frame", frame])
        table = inputs.get("table")
        if table is not None and int(table) != 0:
            command.extend(["-table", str(int(table))])
        if inputs.get("trim"):
            command.append("-trim")
        return command

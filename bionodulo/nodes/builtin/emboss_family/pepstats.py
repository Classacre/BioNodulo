"""EMBOSS pepstats owner: protein statistics report.

``pepstats`` declares ``-outfile`` as a *mandatory* qualifier: with no
``-outfile`` on a non-interactive stdin it prompts and dies.  EMBOSS treats the
literal value ``stdout`` as a request to write the report to standard output,
so this node passes ``-outfile stdout`` and declares ``STDOUT_OUTPUT_INDEX`` so
the workflow engine captures the report into the planned output file.
"""

from __future__ import annotations

from typing import Any

from .adapter import EMBOSS_VERSION, EmbossBase


class EmbossPepstatsNode(EmbossBase):
    """Report physicochemical statistics for a protein sequence."""

    NODE_ID = "emboss_pepstats"
    DISPLAY_NAME = "EMBOSS Pepstats"
    CATEGORY = "emboss"
    DESCRIPTION = "Calculate protein statistics such as molecular weight, isoelectric point, and residue composition"
    SEARCH_ALIASES = ["emboss", "pepstats", "protein statistics", "molecular weight", "isoelectric point", "composition"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("pepstats_report",)
    OUTPUT_FILENAMES = ("pepstats_report.stats.txt",)
    # pepstats writes to `-outfile`; the value `stdout` sends the report to the
    # standard output stream, which the engine redirects to the planned file.
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["pepstats"]
    REQUIRED_CONDA_PACKAGES = ["emboss"]
    VERSION = EMBOSS_VERSION
    DOCUMENTATION_URL = "https://emboss.sourceforge.net/apps/release/6.6/emboss/apps/pepstats.html"
    UPSTREAM_MANPAGE = "doc/manuals/emboss_doc/pepstats.html"
    UPSTREAM_SOURCE = "emboss/emboss/pepstats.c"
    KNOWLEDGE = {
        **EmbossBase.KNOWLEDGE,
        "tool_id": "https://bio.tools/pepstats",
        "topics": [{"uri": "http://edamontology.org/topic_0123", "label": "Protein properties"}],
        "operations": [
            {"uri": "http://edamontology.org/operation_0250", "label": "Protein property calculation"}
        ],
        "citation_evidence": [
            {
                "identifier": "10.1016/S0168-9525(00)02024-2",
                "source_url": "https://bio.tools/pepstats",
                "checked_at": "2026-09-25",
                "note": (
                    "The bio.tools 'pepstats' record lists the EMBOSS Trends in Genetics 2000 "
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
                    {"description": "Input protein sequence file (FASTA)"},
                ),
            },
            "optional": {
                "mono": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Use monoisotopic residue weights (EMBOSS -mono)",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = [
            "pepstats",
            "-sequence",
            str(inputs.get("sequence", "")),
            "-outfile",
            "stdout",
        ]
        if inputs.get("mono"):
            command.append("-mono")
        return command

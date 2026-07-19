"""Focused Samtools 1.23.1 owner: Replace the header in a BAM file from a SAM/BAM source."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
)


class SamtoolsReheaderNode(SamtoolsCommandNode):
    """Replace the header in a BAM file from a SAM/BAM source."""

    NODE_ID = "samtools_reheader"
    DISPLAY_NAME = "Samtools Reheader"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Replace the header of a BAM file using a SAM or BAM source header."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "reheader", "SAM header", "BAM header"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("reheadered_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-reheader.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("reheadered.bam",)
    SHELL = True
    UPSTREAM_MANPAGE = "doc/samtools-reheader.1"
    UPSTREAM_SOURCE = "bam_reheader.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["samtools", "reheader"]
        if inputs.get("no_pg"):
            cmd.append("--no-PG")
        cmd.extend(
            [
                str(inputs.get("input_header", "")),
                str(inputs.get("input_file", inputs.get("bam", ""))),
                ">",
                str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
            ]
        )
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_header": (
                    ("SAM", "BAM", "CRAM"),
                    {"description": "SAM/BAM/CRAM file whose header replaces the target header"},
                ),
                "input_file": ("BAM", {"description": "Target BAM file whose header will be replaced"}),
            },
            "optional": {
                "no_pg": (
                    "BOOLEAN",
                    {"default": False, "description": "Keep the replacement header unmodified by omitting @PG edits"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

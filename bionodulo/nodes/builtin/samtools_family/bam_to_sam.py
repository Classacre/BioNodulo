"""Focused Samtools 1.23.1 owner: Convert BAM alignments to SAM text format."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
)


class SamtoolsBamToSamNode(SamtoolsCommandNode):
    """Convert BAM alignments to SAM text format."""

    NODE_ID = "samtools_bam_to_sam"
    DISPLAY_NAME = "Samtools BAM to SAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Convert BAM alignments to SAM text format with Galaxy-compatible header handling."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "samtools",
        "BAM to SAM",
        "SAM output",
        "header only",
        "include header",
    ]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("sam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("output.sam",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        header = str(inputs.get("header", "-h"))
        cmd = [
            "samtools",
            "view",
            "-o",
            str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0]),
        ]
        if header:
            cmd.append(header)
        cmd.append(str(inputs.get("input", "")))
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if str(inputs.get("header", "-h")) not in {"-h", "-H", ""}:
            return "header must be one of -h, -H, or an empty string"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "BAM alignment file to convert"}),
            },
            "optional": {
                "header": (
                    "STRING",
                    {
                        "default": "-h",
                        "options": ["-h", "-H", ""],
                        "description": "Include the SAM header, return the header only, or exclude the header",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

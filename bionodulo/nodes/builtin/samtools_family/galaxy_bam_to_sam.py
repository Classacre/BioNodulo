"""Focused Samtools 1.23.1 owner: Galaxy wrapper parity node for BAM-to-SAM conversion."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    TOOLS_IUC_GIT_COMMIT,
    TOOLS_IUC_GIT_URL,
)


class GalaxyBamToSamNode(SamtoolsCommandNode):
    """Galaxy wrapper parity node for BAM-to-SAM conversion."""

    NODE_ID = "bam_to_sam"
    DISPLAY_NAME = "BAM-to-SAM"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Convert a BAM dataset to SAM text using the Galaxy BAM-to-SAM wrapper."
    SEARCH_ALIASES = [
        GALAXY_ALIAS,
        "samtools",
        "bam_to_sam",
        "BAM-to-SAM",
        "BAM to SAM",
        "converted SAM",
        "header only",
    ]
    RETURN_TYPES = ("SAM",)
    RETURN_NAMES = ("output1",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/tree/main/tool_collections/samtools/bam_to_sam"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "2.0.7"
    GIT_URL = TOOLS_IUC_GIT_URL
    GIT_COMMIT = TOOLS_IUC_GIT_COMMIT
    OUTPUT_FILENAMES = ("output1.sam",)
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"
    WRAPPER_SOURCE = "tool_collections/samtools/bam_to_sam/bam_to_sam.xml"

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
        cmd.append(str(inputs.get("input1", "")))
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
                "input1": ("BAM", {"description": "BAM file to convert to SAM"}),
            },
            "optional": {
                "header": (
                    "STRING",
                    {
                        "default": "-h",
                        "options": ["-h", "-H", ""],
                        "description": "Include the full SAM output with header, return only the header, or omit the header",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

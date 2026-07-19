"""Focused Samtools 1.23.1 owner: Merge multiple BAM files."""

from __future__ import annotations

from typing import Any

from .adapter import SamtoolsCommandNode, _as_list, validate_path_list


class SamtoolsMergeNode(SamtoolsCommandNode):
    """Merge multiple BAM files."""

    NODE_ID = "samtools_merge"
    DISPLAY_NAME = "Samtools Merge"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Merge multiple sorted BAM files into one"
    SEARCH_ALIASES = ["samtools", "merge", "combine", "bam"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("merged_bam",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-merge.html"
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("merged_bam.bam",)
    UPSTREAM_MANPAGE = "doc/samtools-merge.1"
    UPSTREAM_SOURCE = "bam_sort.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bams": ("BAM_LIST", {"description": "Coordinate-sorted BAM files to merge"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {},
            "hidden": {
                "output": ("STRING", {}),
            },
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = cls.output_dir(inputs)
        return [
            "samtools",
            "merge",
            "-@",
            str(inputs.get("threads", 4)),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            *_as_list(inputs.get("bams")),
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return validate_path_list(inputs, "bams")

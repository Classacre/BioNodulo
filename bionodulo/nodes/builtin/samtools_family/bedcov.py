"""Focused Samtools 1.23.1 owner: Calculate read depth summaries for intervals in a BED file."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _add_if_value,
    _as_list,
    _flag_sum,
    validate_index_pairs,
)


class SamtoolsBedcovNode(SamtoolsCommandNode):
    """Calculate read depth summaries for intervals in a BED file."""

    NODE_ID = "samtools_bedcov"
    DISPLAY_NAME = "Samtools Bedcov"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Calculate read depth totals for BED intervals across one or more BAM files."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "bedcov", "interval coverage", "BED coverage", "depth threshold"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("interval_coverage",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-bedcov.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("interval_coverage.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-bedcov.1"
    UPSTREAM_SOURCE = "bedcov.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["samtools", "bedcov"]
        _add_if_value(cmd, "-Q", inputs.get("mapq"))
        if inputs.get("countdel"):
            cmd.append("-j")
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["-g", str(required_flags)])
        if skipped_flags:
            cmd.extend(["-G", str(skipped_flags)])
        _add_if_value(cmd, "-d", inputs.get("depth_thresh"))
        cmd.append("-X")
        cmd.append(str(inputs.get("input_bed", "")))
        cmd.extend(_as_list(inputs.get("input_bams", inputs.get("bam"))))
        cmd.extend(_as_list(inputs.get("bam_indexes")))
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return validate_index_pairs(
            inputs,
            data_key="input_bams",
            index_key="bam_indexes",
            required=True,
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bed": ("BED", {"description": "BED intervals to summarize"}),
                "input_bams": ("BAM_LIST", {"description": "One or more indexed BAM files"}),
                "bam_indexes": (
                    "FILE_LIST",
                    {"description": "One BAI or CSI index per input BAM, in matching order"},
                ),
            },
            "optional": {
                "mapq": ("INT", {"default": "", "min": 0, "description": "Minimum mapping quality"}),
                "countdel": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude deletions and reference skips from coverage totals"},
                ),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "depth_thresh": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Add a column counting bases with coverage at or above this threshold",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

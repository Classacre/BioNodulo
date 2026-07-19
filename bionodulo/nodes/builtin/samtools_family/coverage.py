"""Focused Samtools 1.23.1 owner: Compute per-reference coverage summaries or ASCII histogram data."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_CITATION_DOIS,
    SAMTOOLS_CITATION_TEXT,
    SAMTOOLS_CITATION_URLS,
    _as_list,
    _flag_sum,
    validate_index_pairs,
)


class SamtoolsCoverageNode(SamtoolsCommandNode):
    """Compute per-reference coverage summaries or ASCII histogram data."""

    NODE_ID = "samtools_coverage"
    DISPLAY_NAME = "Samtools Coverage"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Compute tabular or histogram coverage summaries per reference sequence using samtools coverage."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "coverage", "histogram", "BAM coverage", "chromosome coverage"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("coverage",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-coverage.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("coverage.txt",)
    UPSTREAM_MANPAGE = "doc/samtools-coverage.1"
    UPSTREAM_SOURCE = "coverage.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        input_bams = _as_list(inputs.get("input_bams"))
        cmd = ["samtools", "coverage"]
        cmd.extend(["-l", str(inputs.get("min_read_length", 0))])
        cmd.extend(["-q", str(inputs.get("min_mq", 0))])
        cmd.extend(["-Q", str(inputs.get("min_bq", 0))])
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["--rf", str(required_flags)])
        if skipped_flags:
            cmd.extend(["--ff", str(skipped_flags)])
        if inputs.get("region"):
            cmd.extend(["-r", str(inputs["region"])])
        if inputs.get("histogram"):
            cmd.extend(["-m", "-w", str(inputs.get("n_bins", 100))])
        cmd.extend(["-o", str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0])])
        cmd.extend(input_bams)
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
            required=bool(inputs.get("region")),
            colocated_suffix=".bai",
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM_LIST", {"description": "One or more BAM files to summarize"}),
            },
            "optional": {
                "bam_indexes": (
                    "FILE_LIST",
                    {"description": ("Exact colocated <bam>.bai indexes; required when a region is requested")},
                ),
                "min_read_length": ("INT", {"default": 0, "min": 0}),
                "min_mq": ("INT", {"default": 0, "min": 0, "description": "Minimum mapping quality"}),
                "min_bq": ("INT", {"default": 0, "min": 0, "description": "Minimum base quality"}),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Include reads with at least one listed SAM flag", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "region": ("STRING", {"default": "", "description": "Region such as chr1:100-200"}),
                "histogram": ("BOOLEAN", {"default": False, "description": "Emit histogram data"}),
                "n_bins": ("INT", {"default": 100, "min": 1, "description": "Number of histogram bins"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

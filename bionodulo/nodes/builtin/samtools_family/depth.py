"""Focused Samtools 1.23.1 owner: Compute per-position read depth across one or more BAM files."""

from __future__ import annotations

from typing import Any

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_CITATION_DOIS,
    SAMTOOLS_CITATION_TEXT,
    SAMTOOLS_CITATION_URLS,
    _add_if_value,
    _as_list,
    _flag_sum,
    validate_index_pairs,
)


class SamtoolsDepthNode(SamtoolsCommandNode):
    """Compute per-position read depth across one or more BAM files."""

    NODE_ID = "samtools_depth"
    DISPLAY_NAME = "Samtools Depth"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Compute per-position alignment depth for one or more BAM files, optionally restricted to regions."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "depth", "coverage depth", "per-base coverage", "BAM depth"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("depth",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-depth.html"
    CITATION_DOIS = SAMTOOLS_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("depth.tsv",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-depth.1"
    UPSTREAM_SOURCE = "bam2depth.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["samtools", "depth"]
        all_positions = str(inputs.get("all", ""))
        if all_positions:
            cmd.append(all_positions)
        if inputs.get("input_bed"):
            cmd.extend(["-b", str(inputs["input_bed"])])
        if inputs.get("region"):
            cmd.extend(["-r", str(inputs["region"])])
        _add_if_value(cmd, "-l", inputs.get("minlength"))
        _add_if_value(cmd, "-q", inputs.get("basequality"))
        _add_if_value(cmd, "-Q", inputs.get("mapquality"))
        include_flags = _flag_sum(inputs.get("include_flags"))
        include_any_flags = _flag_sum(inputs.get("include_any_flags"))
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if include_flags:
            cmd.extend(["-g", str(include_flags)])
        if include_any_flags:
            cmd.extend(["--incl-flags", str(include_any_flags)])
        if required_flags:
            cmd.extend(["--require-flags", str(required_flags)])
        if skipped_flags:
            cmd.extend(["-G", str(skipped_flags)])
        if inputs.get("deletions"):
            cmd.append("-J")
        if inputs.get("single_read"):
            cmd.append("-s")
        if inputs.get("header"):
            cmd.append("-H")
        bams = _as_list(inputs.get("input_bams", inputs.get("bam")))
        indexes = _as_list(inputs.get("bam_indexes"))
        if indexes:
            cmd.append("-X")
        cmd.extend(bams)
        cmd.extend(indexes)
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("maxdepth") not in (None, ""):
            return "maxdepth is ignored by samtools depth 1.23.1; use samtools mpileup to cap depth"
        return validate_index_pairs(
            inputs,
            data_key="input_bams",
            index_key="bam_indexes",
            required=bool(inputs.get("region")),
        )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM_LIST", {"description": "One or more indexed BAM files"}),
            },
            "optional": {
                "bam_indexes": (
                    "FILE_LIST",
                    {"description": ("One BAI/CSI/CRAI index per input BAM/CRAM; required for region queries")},
                ),
                "all": (
                    "STRING",
                    {"default": "", "options": ["", "-a", "-aa"], "description": "Emit zero-depth positions"},
                ),
                "region": ("STRING", {"default": "", "description": "Manual region such as chr1:100-200"}),
                "input_bed": ("BED", {"description": "BED regions to restrict depth calculation"}),
                "minlength": ("INT", {"default": "", "min": 0, "description": "Ignore reads shorter than this length"}),
                "maxdepth": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Retired compatibility port; Samtools 1.23.1 ignores -m/-d",
                        "advanced": True,
                    },
                ),
                "basequality": ("INT", {"default": "", "min": 0, "description": "Minimum base quality"}),
                "mapquality": ("INT", {"default": "", "min": 0, "description": "Minimum mapping quality"}),
                "include_flags": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Default-filtered SAM flags to include back with -g",
                        "advanced": True,
                    },
                ),
                "include_any_flags": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Require at least one listed SAM flag",
                        "advanced": True,
                    },
                ),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags that must be set", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "deletions": ("BOOLEAN", {"default": False, "description": "Include deletions in depth calculation"}),
                "single_read": (
                    "BOOLEAN",
                    {"default": False, "description": "Count only one read in overlapping pairs"},
                ),
                "header": ("BOOLEAN", {"default": False, "description": "Print a file header"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

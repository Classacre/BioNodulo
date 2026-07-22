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
        # coverage.c does not implement -X: when a region is requested it
        # discovers the index beside each BAM.  VALIDATE_INPUTS therefore
        # requires exact colocated sidecars rather than pretending these paths
        # can be passed through argv.
        if inputs.get("max_depth") is not None and str(inputs.get("max_depth")) != "":
            cmd.extend(["-d", str(inputs["max_depth"])])
        if inputs.get("min_depth") is not None and str(inputs.get("min_depth")) != "":
            cmd.extend(["--min-depth", str(inputs["min_depth"])])
        if inputs.get("region"):
            cmd.extend(["-r", str(inputs["region"])])
        if inputs.get("plot_depth"):
            cmd.append("-D")
        if inputs.get("ascii"):
            cmd.append("-A")
        histogram_mode = bool(
            inputs.get("histogram") or inputs.get("plot_depth") or inputs.get("ascii")
        )
        if inputs.get("no_header"):
            cmd.append("-H")
        if inputs.get("histogram"):
            cmd.append("-m")
        if histogram_mode:
            cmd.extend(["-w", str(inputs.get("n_bins", 50))])
        cmd.extend(["-o", str(cls.output_dir(inputs) / cls.OUTPUT_FILENAMES[0])])
        cmd.extend(input_bams)
        return cmd

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        histogram_mode = bool(
            inputs.get("histogram") or inputs.get("plot_depth") or inputs.get("ascii")
        )
        if not histogram_mode and inputs.get("n_bins", 50) != 50:
            return "n_bins is only valid for histogram, plot_depth, or ascii output"
        if histogram_mode and inputs.get("no_header"):
            return "no_header only affects tabular coverage output"
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
                    {
                        "default": "",
                        "description": (
                            "Require every listed SAM flag bit; reads with any mask bit unset are skipped"
                        ),
                        "advanced": True,
                    },
                ),
                "skipped_flags": (
                    "STRING",
                    {"default": "", "description": "Comma-separated SAM flags to exclude", "advanced": True},
                ),
                "max_depth": (
                    "INT",
                    {"default": "", "min": 0, "description": "Maximum allowed coverage depth", "advanced": True},
                ),
                "min_depth": (
                    "INT",
                    {
                        "default": "",
                        "min": 1,
                        "description": "Ignore positions below this coverage depth",
                        "advanced": True,
                    },
                ),
                "region": ("STRING", {"default": "", "description": "Region such as chr1:100-200"}),
                "histogram": ("BOOLEAN", {"default": False, "description": "Emit histogram data"}),
                "n_bins": ("INT", {"default": 50, "min": 1, "description": "Number of histogram bins"}),
                "plot_depth": (
                    "BOOLEAN",
                    {"default": False, "description": "Plot depth rather than percent covered", "advanced": True},
                ),
                "ascii": (
                    "BOOLEAN",
                    {"default": False, "description": "Use ASCII-only histogram characters", "advanced": True},
                ),
                "no_header": (
                    "BOOLEAN",
                    {"default": False, "description": "Suppress the tabular header", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

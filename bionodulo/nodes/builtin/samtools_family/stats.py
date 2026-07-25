"""Focused Samtools 1.23.1 owner: Generate comprehensive BAM statistics."""

from __future__ import annotations

from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsStatsNode(SamtoolsCommandNode):
    """Generate comprehensive BAM statistics."""

    NODE_ID = "samtools_stats"
    DISPLAY_NAME = "Samtools Stats"
    CATEGORY = "samtools"
    DESCRIPTION = "Generate comprehensive statistics for a BAM file"
    SEARCH_ALIASES = ["samtools", "stats", "statistics", "bam stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["samtools"]
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-stats.html"
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("stats.stats.txt",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-stats.1"
    UPSTREAM_SOURCE = "stats.c"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "samtools",
            "stats",
            "-@",
            str(inputs.get("threads", 2)),
        ]
        if inputs.get("target_regions"):
            cmd.extend(["-t", str(inputs["target_regions"])])
        cmd.append(str(inputs.get("bam", "")))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "target_regions": (
                    "TSV",
                    {
                        "description": (
                            "Optional 1-based inclusive target table with chromosome, start, and end columns"
                        )
                    },
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }

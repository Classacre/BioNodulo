"""Samtools flagstat node."""

from __future__ import annotations

from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsFlagstatNode(SamtoolsCommandNode):
    """Capture the default text flagstat report from stdout."""

    NODE_ID = "samtools_flagstat"
    DISPLAY_NAME = "Samtools Flagstat"
    DESCRIPTION = "Generate alignment statistics with samtools flagstat"
    SEARCH_ALIASES = ["samtools", "flagstat", "stats", "alignment stats"]
    RETURN_TYPES = ("STATS_FILE",)
    RETURN_NAMES = ("stats",)
    OUTPUT_FILENAMES = ("stats.stats.txt",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-flagstat.html"
    UPSTREAM_MANPAGE = "doc/samtools-flagstat.1"
    UPSTREAM_SOURCE = "bam_stat.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return [
            "samtools",
            "flagstat",
            "-@",
            str(inputs.get("threads", 2)),
            str(inputs.get("bam", "")),
        ]

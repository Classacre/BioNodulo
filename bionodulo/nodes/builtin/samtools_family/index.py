"""Samtools index node with the provisional Task 2 BAI-only contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsIndexNode(SamtoolsCommandNode):
    """Create a BAI for the input coordinate-sorted BAM."""

    NODE_ID = "samtools_index"
    DISPLAY_NAME = "Samtools Index"
    DESCRIPTION = "Create a BAI index for a coordinate-sorted BAM"
    SEARCH_ALIASES = ["samtools", "index", "bai"]
    RETURN_TYPES = ("BAI",)
    RETURN_NAMES = ("bai",)
    OUTPUT_FILENAMES = ("indexed_bam.bam.bai",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-index.html"
    UPSTREAM_MANPAGE = "doc/samtools-index.1"
    UPSTREAM_SOURCE = "bam_index.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Coordinate-sorted BAM file to index"},
                ),
                "threads": ("INT", {"default": 2, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "samtools",
            "index",
            "-@",
            str(inputs.get("threads", 2)),
            "-b",
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            str(inputs.get("bam", "")),
        ]

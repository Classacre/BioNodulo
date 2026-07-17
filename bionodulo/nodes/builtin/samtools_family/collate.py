"""Samtools collate node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsCollateNode(SamtoolsCommandNode):
    """Name-collate BAM alignments before mate fixing."""

    NODE_ID = "samtools_collate"
    DISPLAY_NAME = "Samtools Collate"
    DESCRIPTION = "Name-collate a BAM before samtools fixmate"
    SEARCH_ALIASES = ["samtools", "collate", "name collate", "queryname"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("name_collated_bam",)
    OUTPUT_FILENAMES = ("name_collated_bam.bam",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-collate.html"
    UPSTREAM_MANPAGE = "doc/samtools-collate.1"
    UPSTREAM_SOURCE = "bamshuf.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": ("BAM", {"description": "Input BAM file"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "samtools",
            "collate",
            "-@",
            str(inputs.get("threads", 4)),
            "-T",
            str(output / "tmp"),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            str(inputs.get("bam", "")),
        ]

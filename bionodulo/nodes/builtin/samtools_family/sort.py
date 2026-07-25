"""Samtools sort node."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


_MEMORY_RE = re.compile(r"([0-9]+)([KMG]?)")
_MEMORY_MULTIPLIERS = {"": 1, "K": 1 << 10, "M": 1 << 20, "G": 1 << 30}


class SamtoolsSortNode(SamtoolsCommandNode):
    """Coordinate-sort SAM or BAM alignments."""

    NODE_ID = "samtools_sort"
    DISPLAY_NAME = "Samtools Sort"
    DESCRIPTION = "Sort a SAM or BAM file by genomic coordinate"
    SEARCH_ALIASES = ["samtools", "sort", "bam sort", "coordinate"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("sorted_bam",)
    OUTPUT_FILENAMES = ("sorted_bam.bam",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-sort.html"
    UPSTREAM_MANPAGE = "doc/samtools-sort.1"
    UPSTREAM_SOURCE = "bam_sort.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": (
                    ("SAM", "BAM"),
                    {"description": "Input SAM or BAM alignment file"},
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "memory_per_thread": ("STRING", {"default": "768M"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        memory = inputs.get("memory_per_thread", "768M")
        if not isinstance(memory, str):
            return "memory_per_thread must be a string"
        match = _MEMORY_RE.fullmatch(memory)
        if match is None:
            return "memory_per_thread must be bytes or ASCII digits with one K, M, or G suffix"
        value = int(match.group(1)) * _MEMORY_MULTIPLIERS[match.group(2)]
        if value < 1 << 20:
            return "memory_per_thread must be at least 1 MiB"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            "samtools",
            "sort",
            "-@",
            str(inputs.get("threads", 4)),
            "-m",
            str(inputs.get("memory_per_thread", "768M")),
            "-T",
            str(output / "tmp"),
            "-o",
            str(output / cls.OUTPUT_FILENAMES[0]),
            str(inputs.get("alignment", "")),
        ]

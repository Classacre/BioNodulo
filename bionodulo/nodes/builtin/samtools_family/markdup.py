"""Samtools markdup node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsMarkdupNode(SamtoolsCommandNode):
    """Mark or remove duplicates from a prepared coordinate-sorted BAM."""

    NODE_ID = "samtools_markdup"
    DISPLAY_NAME = "Samtools Markdup"
    DESCRIPTION = "Mark or remove duplicate alignments"
    SEARCH_ALIASES = ["samtools", "markdup", "mark duplicates", "remove duplicates"]
    RETURN_TYPES = ("BAM", "STATS_FILE")
    RETURN_NAMES = ("marked_bam", "duplicate_stats")
    OUTPUT_FILENAMES = ("marked_bam.bam", "duplicate_stats.stats.txt")
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-markdup.html"
    UPSTREAM_MANPAGE = "doc/samtools-markdup.1"
    UPSTREAM_SOURCE = "bam_markdup.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {
                        "description": (
                            "Coordinate-sorted BAM prepared with samtools fixmate -m"
                        )
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "remove_duplicates": ("BOOLEAN", {"default": False}),
                "mark_supplementary": ("BOOLEAN", {"default": False}),
                "optical_distance": ("INT", {"default": 0, "min": 0}),
                "read_coords": ("STRING", {"default": ""}),
                "clear_existing": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        distance = inputs.get("optical_distance", 0)
        if isinstance(distance, bool) or not isinstance(distance, int):
            return "optical_distance must be an integer"
        if distance < 0:
            return "optical_distance must be non-negative"
        if inputs.get("read_coords") and distance == 0:
            return "read_coords requires a positive optical_distance"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "samtools",
            "markdup",
            "-@",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("remove_duplicates", False):
            command.append("-r")
        if inputs.get("mark_supplementary", False):
            command.append("-S")
        distance = inputs.get("optical_distance", 0)
        if distance > 0:
            command.extend(["-d", str(distance)])
        if inputs.get("read_coords"):
            command.extend(["--read-coords", str(inputs["read_coords"])])
        if inputs.get("clear_existing", False):
            command.append("-c")
        command.extend(
            [
                "-f",
                str(output / cls.OUTPUT_FILENAMES[1]),
                str(inputs.get("bam", "")),
                str(output / cls.OUTPUT_FILENAMES[0]),
            ]
        )
        return command

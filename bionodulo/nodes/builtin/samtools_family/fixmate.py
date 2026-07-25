"""Samtools fixmate node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsFixmateNode(SamtoolsCommandNode):
    """Add mate coordinates and optional duplicate-marking tags."""

    NODE_ID = "samtools_fixmate"
    DISPLAY_NAME = "Samtools Fixmate"
    DESCRIPTION = "Add mate coordinates to a name-collated BAM"
    SEARCH_ALIASES = ["samtools", "fixmate", "mate coordinates", "markdup"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("fixmate_bam",)
    OUTPUT_FILENAMES = ("fixmate_bam.bam",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-fixmate.html"
    UPSTREAM_MANPAGE = "doc/samtools-fixmate.1"
    UPSTREAM_SOURCE = "bam_mate.c"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Name-collated BAM from samtools collate"},
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "add_markdup_tags": ("BOOLEAN", {"default": False}),
                "remove_secondary_unmapped": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "samtools",
            "fixmate",
            "-@",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("add_markdup_tags", False):
            command.append("-m")
        if inputs.get("remove_secondary_unmapped", False):
            command.append("-r")
        command.extend(
            [str(inputs.get("bam", "")), str(output / cls.OUTPUT_FILENAMES[0])]
        )
        return command

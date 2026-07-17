"""Samtools view node."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import SamtoolsCommandNode


class SamtoolsViewNode(SamtoolsCommandNode):
    """Convert a SAM or BAM alignment stream to BAM with optional flag filters."""

    NODE_ID = "samtools_view"
    DISPLAY_NAME = "Samtools View"
    DESCRIPTION = "Convert SAM or BAM alignments to BAM and filter by flags"
    SEARCH_ALIASES = ["samtools", "view", "sam to bam", "convert", "filter"]
    RETURN_TYPES = ("BAM",)
    RETURN_NAMES = ("bam",)
    OUTPUT_FILENAMES = ("bam.bam",)
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-view.html"
    UPSTREAM_MANPAGE = "doc/samtools-view.1"
    UPSTREAM_SOURCE = "sam_view.c"

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
                "require_all_flags": ("INT", {"default": None}),
                "exclude_any_flags": ("INT", {"default": None}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        for name in ("require_all_flags", "exclude_any_flags"):
            value = inputs.get(name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int):
                return f"{name} must be an integer"
            if not 0 <= value <= 65535:
                return f"{name} must be between 0 and 65535"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = [
            "samtools",
            "view",
            "-b",
            "-@",
            str(inputs.get("threads", 4)),
        ]
        if inputs.get("require_all_flags") is not None:
            command.extend(["-f", str(inputs["require_all_flags"])])
        if inputs.get("exclude_any_flags") is not None:
            command.extend(["-F", str(inputs["exclude_any_flags"])])
        command.extend(
            ["-o", str(output / cls.OUTPUT_FILENAMES[0]), str(inputs.get("alignment", ""))]
        )
        return command

"""BEDTools closest node pinned to 2.31.1."""

from __future__ import annotations

import os
from typing import Any

from .adapter import BEDToolsCommandNode


class BEDToolsClosestNode(BEDToolsCommandNode):
    """Find the closest presorted annotation interval for each query interval."""

    NODE_ID = "bedtools_closest"
    DISPLAY_NAME = "BEDTools Closest"
    DESCRIPTION = "Find the closest features for chromosome/start-sorted query intervals"
    SEARCH_ALIASES = ["bedtools", "closest", "nearest gene", "nearest feature", "bed annotation"]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("closest",)
    OUTPUT_FILENAMES = ("closest.bed",)
    STDOUT_OUTPUT_INDEX = 0
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/closest.html"
    UPSTREAM_SOURCE = "src/utils/Contexts/ContextClosest.cpp"

    TIE_MODES = ("all", "first", "last")
    STRAND_MODES = ("ignore", "same", "opposite")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "variants": (
                    "BED",
                    {"description": "Query intervals sorted by chromosome and start"},
                ),
                "annotations": (
                    "BED",
                    {"description": "Annotation intervals sorted by chromosome and start"},
                ),
            },
            "optional": {
                "mode": ("STRING", {"default": "all", "options": list(cls.TIE_MODES)}),
                "distance": ("BOOLEAN", {"default": False}),
                "strand": ("STRING", {"default": "ignore", "options": list(cls.STRAND_MODES)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("variants", "annotations"):
            try:
                value = os.fsdecode(os.fspath(inputs.get(key)))
            except TypeError:
                return f"Input '{key}' must be a non-empty path-like value"
            if not value.strip():
                return f"Input '{key}' must be a non-empty path-like value"
        mode = str(inputs.get("mode", "all"))
        if mode not in cls.TIE_MODES:
            return f"Unsupported BEDTools closest tie mode: {mode}"
        strand = str(inputs.get("strand", "ignore"))
        if strand not in cls.STRAND_MODES:
            return f"Unsupported BEDTools closest strand mode: {strand}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = [
            "bedtools",
            "closest",
            "-a",
            str(inputs.get("variants", "")),
            "-b",
            str(inputs.get("annotations", "")),
        ]
        if inputs.get("distance"):
            command.append("-d")
        strand = str(inputs.get("strand", "ignore"))
        if strand == "same":
            command.append("-s")
        elif strand == "opposite":
            command.append("-S")
        command.extend(["-t", str(inputs.get("mode", "all"))])
        return command

"""BEDTools overlap node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsOverlapBedNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_overlapbed"
    DISPLAY_NAME = "BEDTools OverlapBed"
    DESCRIPTION = "Append overlap or distance for two coordinate pairs on each row"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "overlap", "overlapbed", "custom overlap score"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("overlap",)
    OUTPUT_FILENAMES = ("overlap.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/overlap.html"
    UPSTREAM_SOURCE = "src/getOverlap/getOverlap.cpp"
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {}), "cols": ("STRING", {"description": "start1,end1,start2,end2"})},
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_positive_columns(inputs.get("cols"), "cols")
        if validation is not True:
            return validation
        return True if len(cls.csv_values(inputs.get("cols"))) == 4 else "Input 'cols' must contain exactly four columns"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "bedtools", "overlap", "-i", str(inputs["input"]), "-cols", ",".join(cls.csv_values(inputs["cols"])))

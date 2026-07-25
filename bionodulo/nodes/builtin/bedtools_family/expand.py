"""BEDTools expand node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsExpandNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_expandbed"
    DISPLAY_NAME = "BEDTools Expand"
    DESCRIPTION = "Expand comma-delimited values in selected tabular columns"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "expand", "expandbed", "split columns"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("expanded",)
    OUTPUT_FILENAMES = ("expanded.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/expand.html"
    UPSTREAM_SOURCE = "src/expand/expand.cpp"
    REQUIRED_PATH_INPUTS = ("input",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FILE", {}), "columns": ("STRING", {"description": "Positive 1-based columns"})},
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        return cls.validate_positive_columns(inputs.get("columns"), "columns")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(inputs, "bedtools", "expand", "-i", str(inputs["input"]), "-c", ",".join(cls.csv_values(inputs["columns"])))

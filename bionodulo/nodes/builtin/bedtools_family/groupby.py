"""BEDTools groupby node pinned to 2.31.1."""

from __future__ import annotations

from typing import Any

from .adapter import BEDToolsStdoutNode


class BEDToolsGroupByNode(BEDToolsStdoutNode):
    NODE_ID = "bedtools_groupbybed"
    DISPLAY_NAME = "BEDTools GroupBy"
    DESCRIPTION = "Group adjacent equal keys and summarize selected columns"
    SEARCH_ALIASES = ["BioNodulo builtin", "bedtools", "groupby", "groupbybed", "aggregate columns"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("grouped",)
    OUTPUT_FILENAMES = ("grouped.tsv",)
    DOCUMENTATION_URL = "https://bedtools.readthedocs.io/en/latest/content/tools/groupby.html"
    UPSTREAM_SOURCE = "src/groupBy/groupBy.cpp"
    REQUIRED_PATH_INPUTS = ("inputA",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputA": ("FILE", {"description": "Input grouped or sorted by the group columns"}),
                "columns": ("STRING", {}),
                "group": ("STRING", {"default": "1,2,3"}),
                "operation": ("STRING", {"default": "sum"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = cls.validate_positive_columns(inputs.get("group"), "group")
        if validation is not True:
            return validation
        return cls.validate_column_operations(
            inputs.get("columns"),
            inputs.get("operation"),
            operations_key="operation",
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        return cls.checked_command(
            inputs,
            "bedtools", "groupby", "-i", str(inputs["inputA"]),
            "-g", ",".join(cls.csv_values(inputs["group"])),
            "-c", ",".join(cls.csv_values(inputs["columns"])),
            "-o", ",".join(cls.csv_values(inputs["operation"])),
        )

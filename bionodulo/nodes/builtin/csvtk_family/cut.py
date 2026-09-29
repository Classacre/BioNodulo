"""csvtk cut node: select and reorder columns by name."""

from __future__ import annotations

from typing import Any

from .adapter import (
    CSVTK_OPERATION_FEATURE_SELECTION,
    CsvtkStdoutNode,
)


class CsvtkCutNode(CsvtkStdoutNode):
    """Select and arrange columns with csvtk ``cut``."""

    NODE_ID = "csvtk_cut"
    DISPLAY_NAME = "csvtk Cut"
    DESCRIPTION = "Select and reorder columns of a CSV/TSV table by name, in the requested order"
    SEARCH_ALIASES = ["csvtk", "cut", "select columns", "reorder columns", "subset columns"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("selected",)
    OUTPUT_FILENAMES = ("selected.tsv",)
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/csvtk/usage/#cut"
    KNOWLEDGE = {
        **CsvtkStdoutNode.KNOWLEDGE,
        "operations": [CSVTK_OPERATION_FEATURE_SELECTION],
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": (
                    ("CSV", "TSV", "FILE"),
                    {"description": "Input delimited text file"},
                ),
                "columns": (
                    "STRING",
                    {"default": "", "description": "Comma-separated column names, in the desired output order"},
                ),
            },
            "optional": {
                "allow_missing_col": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not error on missing columns"},
                ),
                "ignore_case": (
                    "BOOLEAN",
                    {"default": False, "description": "Match column names case-insensitively"},
                ),
                "delimiter": (
                    "STRING",
                    {"default": "tab", "options": ["tab", "comma"]},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not cls.split_fields(inputs.get("columns")):
            return "Input 'columns' must name at least one column"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["csvtk", "cut", *cls.delimiter_flags(inputs)]
        if inputs.get("allow_missing_col", False):
            command.append("-m")
        if inputs.get("ignore_case", False):
            command.append("-i")
        command.extend(["-f", ",".join(cls.split_fields(inputs.get("columns"))), str(inputs.get("table", ""))])
        return command

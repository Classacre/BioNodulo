"""csvtk headers node: print the column names of a delimited table."""

from __future__ import annotations

from typing import Any

from .adapter import CsvtkStdoutNode


class CsvtkHeadersNode(CsvtkStdoutNode):
    """Print one column name per line from csvtk ``headers``."""

    NODE_ID = "csvtk_headers"
    DISPLAY_NAME = "csvtk Headers"
    DESCRIPTION = "Print the column names of a CSV/TSV table, one name per line"
    SEARCH_ALIASES = ["csvtk", "headers", "header", "column names", "fields"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("headers",)
    OUTPUT_FILENAMES = ("headers.txt",)
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/csvtk/usage/#headers"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": (
                    ("CSV", "TSV", "FILE"),
                    {"description": "Input delimited text file"},
                ),
            },
            "optional": {
                "verbose": ("BOOLEAN", {"default": False, "description": "Print verbose information"}),
                "delimiter": (
                    "STRING",
                    {"default": "tab", "options": ["tab", "comma"]},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        return super().VALIDATE_INPUTS(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        command = ["csvtk", "headers", *cls.delimiter_flags(inputs)]
        if inputs.get("verbose", False):
            command.append("-v")
        command.append(str(inputs.get("table", "")))
        return command

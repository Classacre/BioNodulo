"""csvtk summary node: per-column statistics for a delimited table."""

from __future__ import annotations

from typing import Any

from .adapter import (
    CSVTK_OPERATION_STATISTICAL_CALCULATION,
    SUMMARY_OPERATIONS,
    CsvtkStdoutNode,
)


class CsvtkStatsNode(CsvtkStdoutNode):
    """Compute csvtk ``summary`` statistics for named columns."""

    NODE_ID = "csvtk_stats"
    DISPLAY_NAME = "csvtk Stats"
    DESCRIPTION = "Compute per-column summary statistics (count, min, max, mean, ...) for a CSV/TSV table"
    SEARCH_ALIASES = ["csvtk", "summary", "stats", "statistics", "table stats", "column statistics"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("stats",)
    OUTPUT_FILENAMES = ("stats.tsv",)
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/csvtk/usage/#summary"
    KNOWLEDGE = {
        **CsvtkStdoutNode.KNOWLEDGE,
        "operations": [CSVTK_OPERATION_STATISTICAL_CALCULATION],
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
                    {"default": "", "description": "Comma-separated column names to summarize"},
                ),
            },
            "optional": {
                "operations": (
                    "STRING",
                    {
                        "default": "count,countn,min,max,mean",
                        "description": "Comma-separated csvtk summary operations",
                    },
                ),
                "decimal_width": (
                    "INT",
                    {"default": 2, "min": 0, "max": 10, "description": "Decimal places for float results"},
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

        columns = cls.split_fields(inputs.get("columns"))
        if not columns:
            return "Input 'columns' must name at least one column"

        operations = cls.split_fields(inputs.get("operations", "count,countn,min,max,mean"))
        if not operations:
            return "Input 'operations' must contain at least one operation"
        invalid = [operation for operation in operations if operation not in SUMMARY_OPERATIONS]
        if invalid:
            return f"Input 'operations' contains unsupported value(s): {', '.join(invalid)}"

        width_validation = cls.validate_int(inputs.get("decimal_width", 2), "decimal_width", minimum=0, maximum=10)
        if width_validation is not True:
            return width_validation
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        columns = cls.split_fields(inputs.get("columns"))
        operations = cls.split_fields(inputs.get("operations", "count,countn,min,max,mean"))
        fields = ",".join(f"{column}:{operation}" for column in columns for operation in operations)
        return [
            "csvtk",
            "summary",
            *cls.delimiter_flags(inputs),
            "-w",
            str(inputs.get("decimal_width", 2)),
            "-f",
            fields,
            str(inputs.get("table", "")),
        ]

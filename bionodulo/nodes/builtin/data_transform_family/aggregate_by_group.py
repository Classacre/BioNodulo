"""Ordered group aggregation for strict CSV/TSV tables."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    PythonDataTransformNode,
    as_number,
    delimiter_for,
    node_output_dir,
    path_value,
    read_table,
    validate_choice,
    write_table,
)


AGGREGATIONS = ("count", "sum", "mean", "min", "max")


class AggregateByGroupNode(PythonDataTransformNode):
    """Group rows in first-seen order and calculate one aggregate."""

    NODE_ID = "aggregate_by_group"
    DISPLAY_NAME = "Aggregate by Group"
    DESCRIPTION = "Group table rows in first-seen order and calculate count, sum, mean, min, or max."
    SEARCH_ALIASES = ["aggregate", "group", "summarize", "mean", "count", "table"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("aggregated_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/functions.html"
    UPSTREAM_SOURCE = "built-in len, sum, min, max; ordered dict insertion semantics"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, absent columns, unsupported operations, and non-finite numeric "
        "values are fatal; group order follows first appearance in the input."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "group_by": ("STRING", {"description": "Grouping column"}),
                "operation": (list(AGGREGATIONS), {"default": "mean"}),
            },
            "optional": {
                "value_column": (
                    "STRING",
                    {"default": "", "description": "Numeric column; not used for count"},
                ),
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("table")):
            return "Input 'table' must be a non-empty path-like value"
        if not str(inputs.get("group_by", "")).strip():
            return "Input 'group_by' must be non-empty"
        operation = str(inputs.get("operation", "mean"))
        validation = validate_choice(operation, "operation", AGGREGATIONS)
        if validation is not True:
            return validation
        if operation != "count" and not str(inputs.get("value_column", "")).strip():
            return "Input 'value_column' is required unless operation=count"
        return validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        table = Path(path_value(kwargs["table"])).expanduser()
        fieldnames, rows = read_table(
            table,
            delimiter_for(kwargs.get("delimiter", "auto"), table),
        )
        group_by = str(kwargs["group_by"]).strip()
        value_column = str(kwargs.get("value_column", "") or "").strip()
        operation = str(kwargs.get("operation", "mean"))
        if group_by not in fieldnames:
            raise ValueError(f"Group column {group_by!r} not found")
        if operation != "count" and value_column not in fieldnames:
            raise ValueError(f"Value column {value_column!r} not found")

        groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows:
            groups.setdefault(row.get(group_by, ""), []).append(row)
        output_value_name = f"{operation}_{value_column or 'rows'}"
        output_rows: list[dict[str, Any]] = []
        for key, group_rows in groups.items():
            if operation == "count":
                value: float | int = len(group_rows)
            else:
                try:
                    values = [as_number(row.get(value_column, "")) for row in group_rows]
                except ValueError as exc:
                    raise ValueError(f"Group {key!r} contains an invalid numeric value") from exc
                if operation == "sum":
                    value = sum(values)
                elif operation == "mean":
                    value = sum(values) / len(values)
                elif operation == "min":
                    value = min(values)
                else:
                    value = max(values)
            output_rows.append({group_by: key, output_value_name: value})

        output_path = node_output_dir(self, context) / "aggregated.tsv"
        write_table(output_path, [group_by, output_value_name], output_rows, "\t")
        return (str(output_path),)

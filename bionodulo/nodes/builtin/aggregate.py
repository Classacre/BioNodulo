"""Group-by aggregation utility node."""
from __future__ import annotations

import csv
import math
import statistics
from collections import OrderedDict
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class AggregateNode(BaseNode):
    """Group a table by one or more columns and aggregate values."""

    NODE_ID = "aggregate"
    DISPLAY_NAME = "Aggregate"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Group a table by one or more columns and compute aggregate statistics "
        "such as sum, count, mean, median, min, max, std, var, first, last, and nunique."
    )
    SEARCH_ALIASES = [
        "aggregate",
        "group by",
        "summarize",
        "sum",
        "count",
        "average",
        "mean",
        "median",
        "min",
        "max",
        "stddev",
        "groupby",
        "rollup",
    ]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("aggregated_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    _FUNCTIONS = ["sum", "count", "mean", "median", "min", "max", "std", "var", "first", "last", "nunique"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "group_columns": ("STRING", {"default": "", "description": "Comma-separated group columns"}),
                "agg_column": ("STRING", {"default": "", "description": "Column to aggregate"}),
                "agg_function": ("STRING", {"default": "sum", "options": cls._FUNCTIONS}),
            },
            "optional": {
                "agg_column_2": ("STRING", {"default": ""}),
                "agg_function_2": ("STRING", {"default": "", "options": [""] + cls._FUNCTIONS}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delim = "," if input_path.suffix.lower() == ".csv" else "\t"
        fieldnames, rows = self._read_table(input_path, input_delim)
        group_columns = self._split_csv(str(kwargs.get("group_columns", "")))
        if not group_columns:
            raise ValueError("At least one group column is required")
        self._require_columns(fieldnames, group_columns, "Group column")

        aggregations = self._aggregation_specs(
            fieldnames,
            str(kwargs.get("agg_column", "")),
            str(kwargs.get("agg_function", "sum")),
            str(kwargs.get("agg_column_2", "")),
            str(kwargs.get("agg_function_2", "")),
        )

        groups: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows:
            key = tuple(row.get(column, "") for column in group_columns)
            groups.setdefault(key, []).append(row)

        output_fields = list(group_columns) + [f"{func}_{column}" for column, func in aggregations]
        output_rows: list[dict[str, Any]] = []
        for key, group_rows in groups.items():
            output_row: dict[str, Any] = {column: key[index] for index, column in enumerate(group_columns)}
            for column, func in aggregations:
                output_row[f"{func}_{column}"] = self._aggregate(group_rows, column, func)
            output_rows.append(output_row)

        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        output_path = self._output_dir(context) / f"{input_path.stem}.aggregated{extension}"
        self._write_table(output_path, output_fields, output_rows, output_delim)
        return (str(output_path),)

    @classmethod
    def _aggregation_specs(
        cls,
        fieldnames: list[str],
        agg_column: str,
        agg_function: str,
        agg_column_2: str,
        agg_function_2: str,
    ) -> list[tuple[str, str]]:
        specs: list[tuple[str, str]] = []
        for column, func in [(agg_column, agg_function), (agg_column_2, agg_function_2)]:
            column = column.strip()
            func = func.strip().lower()
            if not column and not func:
                continue
            if not column or not func:
                raise ValueError("Aggregation column and function must both be provided")
            if column not in fieldnames:
                raise ValueError(f"Aggregate column {column!r} not found")
            if func not in cls._FUNCTIONS:
                raise ValueError(f"Unsupported aggregation function: {func}")
            specs.append((column, func))
        if not specs:
            raise ValueError("At least one aggregation column and function is required")
        return specs

    @classmethod
    def _aggregate(cls, rows: list[dict[str, str]], column: str, func: str) -> Any:
        values = [row.get(column, "") for row in rows]
        if func == "count":
            return len(values)
        if func == "first":
            return values[0] if values else ""
        if func == "last":
            return values[-1] if values else ""
        if func == "nunique":
            return len(set(values))

        numbers = [cls._as_number(value) for value in values]
        if func == "sum":
            return sum(numbers)
        if func == "mean":
            return sum(numbers) / len(numbers) if numbers else 0
        if func == "median":
            return statistics.median(numbers) if numbers else 0
        if func == "min":
            return min(numbers)
        if func == "max":
            return max(numbers)
        if func == "std":
            return statistics.stdev(numbers) if len(numbers) > 1 else 0
        if func == "var":
            return statistics.variance(numbers) if len(numbers) > 1 else 0
        raise ValueError(f"Unsupported aggregation function: {func}")

    @staticmethod
    def _read_table(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=delimiter)
            if reader.fieldnames is None:
                raise ValueError(f"Table has no header row: {path}")
            return list(reader.fieldnames), [dict(row) for row in reader]

    @staticmethod
    def _write_table(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], delimiter: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: AggregateNode._format_scalar(row.get(field, "")) for field in fieldnames})

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _require_columns(fieldnames: list[str], columns: list[str], label: str) -> None:
        missing = [column for column in columns if column not in fieldnames]
        if missing:
            raise ValueError(f"{label}(s) not found: {', '.join(missing)}")

    @staticmethod
    def _as_number(value: str) -> float:
        return float(str(value).strip())

    @staticmethod
    def _format_scalar(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isfinite(value) and value.is_integer():
                return str(int(value))
            return str(value)
        return str(value)

    @classmethod
    def _output_dir(cls, context: Any) -> Path:
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = base / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            return (",", ".csv") if input_path.suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")

"""Table reshaping utility node."""
from __future__ import annotations

import csv
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Any

from .adapter import PythonDataTransformNode


class PivotTableNode(PythonDataTransformNode):
    """Reshape CSV/TSV tables between long and wide formats."""

    NODE_ID = "pivot_table"
    DISPLAY_NAME = "Pivot Table"
    CATEGORY = "data_transform"
    DESCRIPTION = "Reshape CSV/TSV tables with pivot, melt, and simple aggregate pivot operations."
    SEARCH_ALIASES = ["pivot", "melt", "wide", "long", "reshape", "table", "csv", "tsv"]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("reshaped_table",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    PRODUCT_SOURCE_COMMIT = "45518cfd3754b40ae44304bd65bc17d5ee6e2816"
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/data_transform_family/pivot_table.py"
    PRODUCT_SOURCE_SYMBOL = "PivotTableNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    RUNTIME_DOCUMENTATION_URLS = (DOCUMENTATION_URL,)
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_csv_runtime": DOCUMENTATION_URL,
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; missing columns, unsupported pivot or "
        "aggregate modes, malformed numeric values, and file I/O errors raise before success."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "operation": (
                    "STRING",
                    {
                        "default": "pivot_wide",
                        "options": ["pivot_wide", "melt_long", "pivot_table_agg"],
                    },
                ),
            },
            "optional": {
                "index_column": ("STRING", {"default": "", "description": "Row ID column for pivot operations"}),
                "index_columns": ("STRING", {"default": "", "description": "Comma-separated row ID columns for pivot operations"}),
                "names_from": ("STRING", {"default": "", "description": "Column whose values become wide headers"}),
                "columns_column": ("STRING", {"default": "", "description": "Column whose values become wide headers"}),
                "values_from": ("STRING", {"default": "", "description": "Column whose values fill pivot cells"}),
                "values_column": ("STRING", {"default": "", "description": "Column whose values fill pivot cells"}),
                "fill_value": ("STRING", {"default": ""}),
                "id_columns": ("STRING", {"default": "", "description": "Comma-separated columns to preserve when melting"}),
                "id_vars": ("STRING", {"default": "", "description": "Comma-separated columns to preserve when melting"}),
                "value_columns": ("STRING", {"default": "", "description": "Comma-separated columns to melt"}),
                "value_vars": ("STRING", {"default": "", "description": "Comma-separated columns to melt"}),
                "variable_name": ("STRING", {"default": "variable"}),
                "var_name": ("STRING", {"default": "", "description": "Name of the long-format variable column"}),
                "value_name": ("STRING", {"default": "value"}),
                "agg_func": ("STRING", {"default": "sum", "options": ["sum", "mean", "count", "min", "max", "median", "std"]}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delimiter = self._delimiter(str(kwargs.get("delimiter", "auto")), input_path)
        fieldnames, rows = self._read_table(input_path, input_delimiter)

        operation = str(kwargs.get("operation", "pivot_wide") or "pivot_wide")
        if operation == "pivot_wide":
            suffix = "wide"
            out_fields, out_rows = self._pivot_wide(
                fieldnames,
                rows,
                self._first_value(kwargs, "index_column", "index_columns"),
                self._first_value(kwargs, "names_from", "columns_column"),
                self._first_value(kwargs, "values_from", "values_column"),
                str(kwargs.get("fill_value", "") or ""),
                aggregate=False,
            )
        elif operation == "melt_long":
            suffix = "long"
            out_fields, out_rows = self._melt_long(
                fieldnames,
                rows,
                self._first_value(kwargs, "id_columns", "id_vars"),
                self._first_value(kwargs, "value_columns", "value_vars"),
                self._first_value(kwargs, "variable_name", "var_name", default="variable"),
                str(kwargs.get("value_name", "value") or "value"),
            )
        elif operation == "pivot_table_agg":
            suffix = "pivot"
            out_fields, out_rows = self._pivot_wide(
                fieldnames,
                rows,
                self._first_value(kwargs, "index_column", "index_columns"),
                self._first_value(kwargs, "names_from", "columns_column"),
                self._first_value(kwargs, "values_from", "values_column"),
                str(kwargs.get("fill_value", "") or ""),
                aggregate=True,
                agg_func=str(kwargs.get("agg_func", "sum") or "sum"),
            )
        else:
            raise ValueError(f"Unsupported pivot operation: {operation}")

        output_delimiter, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        out_path = self._output_dir(context) / f"{input_path.stem}.{suffix}{extension}"
        self._write_table(out_path, out_fields, out_rows, output_delimiter)
        return (str(out_path),)

    @classmethod
    def _output_dir(cls, context: Any) -> Path:
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = base / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _delimiter(value: str, path: Path) -> str:
        normalized = value.strip().lower()
        if normalized == "csv":
            return ","
        if normalized == "tsv":
            return "\t"
        if path.suffix.lower() == ".csv":
            return ","
        return "\t"

    @staticmethod
    def _output_format(value: str, input_path: Path) -> tuple[str, str]:
        normalized = value.strip().upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            return (",", ".csv") if input_path.suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {value}")

    @staticmethod
    def _split_columns(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _first_value(kwargs: dict[str, Any], *names: str, default: str = "") -> str:
        for name in names:
            value = str(kwargs.get(name, "") or "").strip()
            if value:
                return value
        return default

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
                writer.writerow({name: str(row.get(name, "")) for name in fieldnames})

    def _pivot_wide(
        self,
        fieldnames: list[str],
        rows: list[dict[str, str]],
        index_column: str,
        names_from: str,
        values_from: str,
        fill_value: str,
        aggregate: bool,
        agg_func: str = "sum",
    ) -> tuple[list[str], list[dict[str, Any]]]:
        index_columns = self._split_columns(index_column)
        self._require_columns(fieldnames, [*index_columns, names_from, values_from])
        wide_columns = list(OrderedDict((row.get(names_from, ""), None) for row in rows if row.get(names_from, "")).keys())
        grouped: OrderedDict[tuple[str, ...], dict[str, Any]] = OrderedDict()
        aggregate_values: dict[tuple[tuple[str, ...], str], list[float]] = defaultdict(list)

        for row in rows:
            index_value = tuple(row.get(column, "") for column in index_columns)
            wide_name = row.get(names_from, "")
            if index_value not in grouped:
                grouped[index_value] = {
                    column: row.get(column, "")
                    for column in index_columns
                }
            if aggregate:
                aggregate_values[(index_value, wide_name)].append(self._as_number(row.get(values_from, "")))
            elif wide_name not in grouped[index_value]:
                grouped[index_value][wide_name] = row.get(values_from, "")

        if aggregate:
            for (index_value, wide_name), values in aggregate_values.items():
                grouped[index_value][wide_name] = self._aggregate(values, agg_func)

        output_rows = []
        for row in grouped.values():
            output_rows.append({column: row.get(column, fill_value) for column in [*index_columns, *wide_columns]})
        return [*index_columns, *wide_columns], output_rows

    def _melt_long(
        self,
        fieldnames: list[str],
        rows: list[dict[str, str]],
        id_columns_value: str,
        value_columns_value: str,
        variable_name: str,
        value_name: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        id_columns = self._split_columns(id_columns_value)
        if not id_columns:
            raise ValueError("id_columns is required for melt_long")
        value_columns = self._split_columns(value_columns_value)
        if not value_columns:
            value_columns = [name for name in fieldnames if name not in id_columns]
        self._require_columns(fieldnames, [*id_columns, *value_columns])

        output_rows: list[dict[str, Any]] = []
        for row in rows:
            id_values = {column: row.get(column, "") for column in id_columns}
            for column in value_columns:
                output_rows.append({**id_values, variable_name: column, value_name: row.get(column, "")})
        return [*id_columns, variable_name, value_name], output_rows

    @staticmethod
    def _require_columns(fieldnames: list[str], columns: list[str]) -> None:
        missing = [column for column in columns if not column or column not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found in table: {', '.join(repr(column) for column in missing)}")

    @staticmethod
    def _as_number(value: Any) -> float:
        return float(str(value).strip())

    @staticmethod
    def _aggregate(values: list[float], agg_func: str) -> str:
        if agg_func == "sum":
            result = sum(values)
        elif agg_func == "mean":
            result = sum(values) / len(values) if values else 0.0
        elif agg_func == "count":
            result = float(len(values))
        elif agg_func == "min":
            result = min(values) if values else 0.0
        elif agg_func == "max":
            result = max(values) if values else 0.0
        elif agg_func == "median":
            if not values:
                result = 0.0
            else:
                sorted_values = sorted(values)
                midpoint = len(sorted_values) // 2
                if len(sorted_values) % 2:
                    result = sorted_values[midpoint]
                else:
                    result = (sorted_values[midpoint - 1] + sorted_values[midpoint]) / 2
        elif agg_func == "std":
            if len(values) < 2:
                result = 0.0
            else:
                mean = sum(values) / len(values)
                variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
                result = variance ** 0.5
        else:
            raise ValueError(f"Unsupported agg_func: {agg_func}")
        if result.is_integer():
            return str(int(result))
        return str(result)


class ReshapeTableNode(PivotTableNode):
    """Proposal-compatible table reshape node with wide/long terminology."""

    NODE_ID = "reshape_table"
    DISPLAY_NAME = "Reshape Table"
    VERSION = "1.0.0"
    PRODUCT_SOURCE_SYMBOL = "ReshapeTableNode"
    UPSTREAM_SOURCE = f"{PivotTableNode.PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    SOURCE_AUTHORITIES = {
        "product_contract": PivotTableNode.SOURCE_URL,
        "python_csv_runtime": PivotTableNode.DOCUMENTATION_URL,
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; unsupported directions, missing reshape "
        "columns, malformed tables, and file I/O errors raise before success."
    )
    DESCRIPTION = "Convert tables between wide and long formats using melt and pivot operations."
    SEARCH_ALIASES = ["reshape", "melt", "pivot_longer", "pivot_wider", "wide", "long", "table", "csv", "tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "direction": ("STRING", {"default": "long", "options": ["long", "wide"]}),
                "id_vars": ("STRING", {"description": "Comma-separated columns to preserve as identifiers"}),
            },
            "optional": {
                "value_vars": ("STRING", {"default": "", "description": "Columns to gather when reshaping long"}),
                "names_to": ("STRING", {"default": "variable", "description": "Name of the long-format variable column"}),
                "values_to": ("STRING", {"default": "value", "description": "Name of the long-format value column"}),
                "names_from": ("STRING", {"default": "", "description": "Column whose values become wide headers"}),
                "values_from": ("STRING", {"default": "", "description": "Column whose values fill wide cells"}),
                "fill_value": ("STRING", {"default": ""}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delimiter = self._delimiter(str(kwargs.get("delimiter", "auto")), input_path)
        fieldnames, rows = self._read_table(input_path, input_delimiter)

        direction = str(kwargs.get("direction", "long") or "long").lower()
        if direction == "long":
            suffix = "long"
            out_fields, out_rows = self._melt_long(
                fieldnames,
                rows,
                str(kwargs.get("id_vars", "") or ""),
                str(kwargs.get("value_vars", "") or ""),
                str(kwargs.get("names_to", "variable") or "variable"),
                str(kwargs.get("values_to", "value") or "value"),
            )
        elif direction == "wide":
            suffix = "wide"
            out_fields, out_rows = self._pivot_wide(
                fieldnames,
                rows,
                str(kwargs.get("id_vars", "") or ""),
                str(kwargs.get("names_from", "") or ""),
                str(kwargs.get("values_from", "") or ""),
                str(kwargs.get("fill_value", "") or ""),
                aggregate=False,
            )
        else:
            raise ValueError(f"Unsupported reshape direction: {direction}")

        output_delimiter, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        out_path = self._output_dir(context) / f"{input_path.stem}.{suffix}{extension}"
        self._write_table(out_path, out_fields, out_rows, output_delimiter)
        return (str(out_path),)

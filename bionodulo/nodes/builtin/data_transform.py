"""Data transformation and primitive utility nodes for BioNodulo.

These nodes cover the first Phase 1 gap-analysis utilities that do not
require executor-level control-flow changes or external dependencies.
"""
from __future__ import annotations

import ast
import csv
import json
import math
import operator
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import _shell_join
from bionodulo.nodes.types import file_extension_for


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _delimiter(value: str, path: str | Path | None = None) -> str:
    mode = (value or "auto").strip().lower()
    if mode == "csv":
        return ","
    if mode == "tsv":
        return "	"
    if path and str(path).lower().endswith(".csv"):
        return ","
    return "	"


def _read_table(path: str | Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError(f"Table has no header row: {path}")
        return list(reader.fieldnames), [dict(row) for row in reader]


def _write_table(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _format_scalar(row.get(name, "")) for name in fieldnames})


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _parse_rename_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in _split_csv(value):
        if ":" not in item:
            raise ValueError(f"Rename entry must be old:new, got {item!r}")
        old, new = item.split(":", 1)
        old = old.strip()
        new = new.strip()
        if not old or not new:
            raise ValueError(f"Rename entry must be old:new, got {item!r}")
        mapping[old] = new
    return mapping


def _format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _as_number(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    return float(str(value).strip())


def _normalise_table_format(value: str, path: str | Path | None = None) -> str:
    requested = str(value or "auto").strip().lower()
    if requested == "auto":
        suffixes = "".join(Path(str(path)).suffixes).lower() if path else ""
        if suffixes.endswith(".json"):
            return "json"
        if suffixes.endswith(".csv"):
            return "csv"
        return "tsv"
    if requested not in {"csv", "tsv", "json"}:
        raise ValueError(f"Unsupported table format: {value}")
    return requested


def _fieldnames_from_records(records: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            name = str(key)
            if name not in seen:
                seen.add(name)
                fieldnames.append(name)
    return fieldnames


def _read_records(path: str | Path, input_format: str) -> list[dict[str, Any]]:
    if input_format in {"csv", "tsv"}:
        _fieldnames, rows = _read_table(path, "," if input_format == "csv" else "	")
        return rows

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("JSON input must be an object, a list of objects, or an object with a rows list")
    return [dict(item) for item in payload]


def _write_records(path: Path, output_format: str, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return

    fieldnames = _fieldnames_from_records(records)
    _write_table(path, fieldnames, records, "," if output_format == "csv" else "	")


def _fasta_header(value: Any) -> str:
    header = re.sub(r"\s+", "_", str(value or "").strip())
    header = re.sub(r"[^A-Za-z0-9_.|:-]", "_", header)
    return header or "sequence"


def _fasta_sequence(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def _wrap_sequence(sequence: str, line_width: int) -> list[str]:
    if line_width <= 0:
        return [sequence]
    return [sequence[index:index + line_width] for index in range(0, len(sequence), line_width)]


class FilterRowsNode(BaseNode):
    """Filter CSV/TSV rows by a column condition."""

    NODE_ID = "filter_rows"
    DISPLAY_NAME = "Filter Rows"
    CATEGORY = "data_transform"
    DESCRIPTION = "Filter CSV/TSV rows using numeric, string, regex, or emptiness conditions."
    SEARCH_ALIASES = [
        "filter",
        "rows",
        "table",
        "csv",
        "tsv",
        "quality gate",
        "subset rows",
        "select rows",
        "where",
        "query",
        "conditional filter",
        "table filter",
        "csv filter",
        "tsv filter",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("filtered_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "column": ("STRING", {"description": "Column to test"}),
                "operator": ("STRING", {
                    "default": "equals",
                    "options": [
                        "equals", "not_equals", "==", "!=", "contains", "not_contains",
                        "startswith", "endswith", "regex", "greater_than", ">",
                        "greater_or_equal", ">=", "less_than", "<", "less_or_equal", "<=",
                        "in", "not_in", "is_empty", "is_not_empty", "is_null", "is_not_null",
                    ],
                }),
                "value": ("STRING", {"default": "", "description": "Comparison value"}),
            },
            "optional": {
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
                "invert": ("BOOLEAN", {"default": False}),
                "logical_op": ("STRING", {"default": "AND", "options": ["AND", "OR"]}),
                "column_2": ("STRING", {"default": ""}),
                "operator_2": ("STRING", {
                    "default": "",
                    "options": [
                        "", "equals", "not_equals", "==", "!=", "contains", "not_contains",
                        "startswith", "endswith", "regex", "greater_than", ">",
                        "greater_or_equal", ">=", "less_than", "<", "less_or_equal", "<=",
                        "in", "not_in", "is_empty", "is_not_empty", "is_null", "is_not_null",
                    ],
                }),
                "value_2": ("STRING", {"default": ""}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table = kwargs["table"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table)
        fieldnames, rows = _read_table(table, delim)
        column = str(kwargs["column"])
        if column not in fieldnames:
            raise ValueError(f"Column {column!r} not found in table")

        operator_name = str(kwargs.get("operator", "equals"))
        expected = str(kwargs.get("value", ""))
        column_2 = str(kwargs.get("column_2", "") or "")
        operator_2 = str(kwargs.get("operator_2", "") or "")
        expected_2 = str(kwargs.get("value_2", ""))
        logical_op = str(kwargs.get("logical_op", "AND") or "AND").upper()
        case_sensitive = bool(kwargs.get("case_sensitive", True))
        invert = bool(kwargs.get("invert", False))
        if logical_op not in {"AND", "OR"}:
            raise ValueError(f"Unsupported logical_op: {logical_op}")
        if operator_2:
            if not column_2:
                raise ValueError("column_2 is required when operator_2 is set")
            if column_2 not in fieldnames:
                raise ValueError(f"Column {column_2!r} not found in table")

        filtered: list[dict[str, str]] = []
        for row in rows:
            passed = self._matches(row.get(column, ""), operator_name, expected, case_sensitive)
            if operator_2:
                second_passed = self._matches(row.get(column_2, ""), operator_2, expected_2, case_sensitive)
                passed = passed and second_passed if logical_op == "AND" else passed or second_passed
            if invert:
                passed = not passed
            if passed:
                filtered.append(row)

        if "output_type" in kwargs:
            output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), table)
            output_name = f"{Path(str(table)).stem}.filtered{extension}"
        else:
            output_delim = "\t"
            output_name = "filtered.tsv"
        out_path = _node_output_dir(self, context) / output_name
        _write_table(out_path, fieldnames, filtered, output_delim)
        return (str(out_path),)

    @staticmethod
    def _matches(actual: str, operator_name: str, expected: str, case_sensitive: bool) -> bool:
        operator_name = FilterRowsNode._normalise_operator(operator_name)
        text = str(actual or "")
        compare_to = str(expected or "")
        if not case_sensitive:
            text_cmp = text.lower()
            expected_cmp = compare_to.lower()
        else:
            text_cmp = text
            expected_cmp = compare_to

        if operator_name == "equals":
            return text_cmp == expected_cmp
        if operator_name == "not_equals":
            return text_cmp != expected_cmp
        if operator_name == "contains":
            return expected_cmp in text_cmp
        if operator_name == "not_contains":
            return expected_cmp not in text_cmp
        if operator_name == "startswith":
            return text_cmp.startswith(expected_cmp)
        if operator_name == "endswith":
            return text_cmp.endswith(expected_cmp)
        if operator_name == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            return re.search(compare_to, text, flags=flags) is not None
        if operator_name in {"is_empty", "is_null"}:
            return text.strip() == ""
        if operator_name in {"is_not_empty", "is_not_null"}:
            return text.strip() != ""
        if operator_name in {"in", "not_in"}:
            values = _split_csv(expected_cmp)
            matched = text_cmp in values
            return matched if operator_name == "in" else not matched

        comparisons: dict[str, Callable[[float, float], bool]] = {
            "greater_than": operator.gt,
            "greater_or_equal": operator.ge,
            "less_than": operator.lt,
            "less_or_equal": operator.le,
        }
        if operator_name in comparisons:
            try:
                return comparisons[operator_name](_as_number(text), _as_number(compare_to))
            except ValueError:
                return False
        raise ValueError(f"Unsupported filter operator: {operator_name}")

    @staticmethod
    def _normalise_operator(operator_name: str) -> str:
        aliases = {
            "==": "equals",
            "!=": "not_equals",
            ">": "greater_than",
            ">=": "greater_or_equal",
            "<": "less_than",
            "<=": "less_or_equal",
            "is_null": "is_empty",
            "is_not_null": "is_not_empty",
        }
        return aliases.get(str(operator_name or "").strip(), str(operator_name or "").strip())

    @staticmethod
    def _output_format(output_type: str, input_path: str | Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            return (",", ".csv") if Path(str(input_path)).suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")


class ExtractColumnsNode(BaseNode):
    """Select, reorder, and rename columns from a CSV/TSV table."""

    NODE_ID = "extract_columns"
    DISPLAY_NAME = "Extract Columns"
    CATEGORY = "data_transform"
    DESCRIPTION = "Select, reorder, and optionally rename columns from a CSV/TSV table."
    SEARCH_ALIASES = ["columns", "select", "rename", "table", "csv", "tsv"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("extracted_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "columns": ("STRING", {"description": "Comma-separated columns in output order"}),
            },
            "optional": {
                "rename_map": ("STRING", {"default": "", "description": "Comma-separated old:new renames"}),
                "column_indices": ("STRING", {"default": "", "description": "Comma-separated 0-based column indices"}),
                "rename_to": ("STRING", {"default": "", "description": "Comma-separated output column names"}),
                "drop_mode": ("BOOLEAN", {"default": False, "description": "Drop selected columns instead of keeping them"}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table = kwargs["table"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table)
        fieldnames, rows = _read_table(table, delim)
        selected = self._selected_columns(
            fieldnames,
            str(kwargs.get("columns", "") or ""),
            str(kwargs.get("column_indices", "") or ""),
        )
        missing = [name for name in selected if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")
        if kwargs.get("drop_mode", False):
            selected = [name for name in fieldnames if name not in set(selected)]
        rename_map = _parse_rename_map(str(kwargs.get("rename_map", "")))
        output_fields = self._output_fields(selected, rename_map, str(kwargs.get("rename_to", "") or ""))
        output_rows = [
            {output_name: row.get(source_name, "") for source_name, output_name in zip(selected, output_fields)}
            for row in rows
        ]
        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), table)
        out_path = _node_output_dir(self, context) / f"{Path(str(table)).stem}.extracted{extension}"
        _write_table(out_path, output_fields, output_rows, output_delim)
        return (str(out_path),)

    @staticmethod
    def _selected_columns(fieldnames: list[str], columns: str, column_indices: str) -> list[str]:
        if column_indices.strip():
            selected: list[str] = []
            for item in _split_csv(column_indices):
                try:
                    index = int(item)
                except ValueError as exc:
                    raise ValueError(f"Column index must be an integer: {item}") from exc
                if index < 0 or index >= len(fieldnames):
                    raise ValueError(f"Column index out of range: {index}")
                selected.append(fieldnames[index])
            return selected
        columns = columns.strip()
        if columns == "*":
            return list(fieldnames)
        if columns.startswith(":"):
            try:
                limit = int(columns[1:])
            except ValueError as exc:
                raise ValueError(f"Column range must be :N, got {columns!r}") from exc
            if limit < 0:
                raise ValueError(f"Column range must be non-negative: {columns!r}")
            return list(fieldnames[:limit])
        return _split_csv(columns)

    @staticmethod
    def _output_fields(selected: list[str], rename_map: dict[str, str], rename_to: str) -> list[str]:
        positional_names = _split_csv(rename_to)
        if positional_names:
            if len(positional_names) != len(selected):
                raise ValueError(
                    f"rename_to length ({len(positional_names)}) must match selected columns ({len(selected)})"
                )
            return positional_names
        return [rename_map.get(name, name) for name in selected]

    @staticmethod
    def _output_format(output_type: str, input_path: str | Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            return (",", ".csv") if Path(str(input_path)).suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")


class MergeTablesNode(BaseNode):
    """Join two CSV/TSV tables by a shared key column."""

    NODE_ID = "merge_tables"
    DISPLAY_NAME = "Merge Tables"
    CATEGORY = "data_transform"
    DESCRIPTION = "Join two CSV/TSV tables by a shared or mapped key using inner, left, right, or outer joins."
    SEARCH_ALIASES = ["merge", "join", "table", "csv", "tsv", "annotation", "left join", "right join", "outer join"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("merged_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table_a": ("FILE", {"description": "Left CSV/TSV table"}),
                "table_b": ("FILE", {"description": "Right CSV/TSV table"}),
            },
            "optional": {
                "join_key": ("STRING", {
                    "default": "",
                    "description": "Shared column name to join on; empty auto-detects a common column",
                }),
                "key_column_a": ("STRING", {
                    "default": "",
                    "description": "Column name in table A; empty uses join_key or auto-detected common column",
                }),
                "key_column_b": ("STRING", {
                    "default": "",
                    "description": "Column name in table B; empty uses key_column_a/join_key",
                }),
                "join_type": ("STRING", {"default": "inner", "options": ["inner", "left", "right", "outer"]}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "right_suffix": ("STRING", {"default": "_right", "advanced": True}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table_a = kwargs["table_a"]
        table_b = kwargs["table_b"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table_a)
        fields_a, rows_a = _read_table(table_a, delim)
        fields_b, rows_b = _read_table(table_b, delim)
        key_a, key_b = self._resolve_join_keys(kwargs, fields_a, fields_b)
        join_type = str(kwargs.get("join_type", "inner"))
        suffix = str(kwargs.get("right_suffix", "_right"))
        if join_type not in {"inner", "left", "right", "outer"}:
            raise ValueError(f"Unsupported join_type: {join_type}")

        right_output_names = {
            field: (field if field not in fields_a else f"{field}{suffix}")
            for field in fields_b
            if field != key_b
        }
        output_fields = list(fields_a) + list(right_output_names.values())

        right_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(row.get(key_b, ""), []).append(row)
        left_by_key: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows_a:
            left_by_key.setdefault(row.get(key_a, ""), []).append(row)

        output_rows: list[dict[str, Any]] = []
        if join_type in {"inner", "left", "outer"}:
            for left in rows_a:
                matches = right_by_key.get(left.get(key_a, ""), [])
                if matches:
                    for right in matches:
                        output_rows.append(self._combine(left, right, fields_a, right_output_names))
                elif join_type in {"left", "outer"}:
                    output_rows.append(self._combine(left, None, fields_a, right_output_names))

        if join_type in {"right", "outer"}:
            for right in rows_b:
                matches = left_by_key.get(right.get(key_b, ""), [])
                if join_type == "right" and matches:
                    for left in matches:
                        output_rows.append(self._combine(left, right, fields_a, right_output_names))
                elif not matches:
                    left_stub = {field: "" for field in fields_a}
                    left_stub[key_a] = right.get(key_b, "")
                    output_rows.append(self._combine(left_stub, right, fields_a, right_output_names))

        output_delim, extension = self._output_format(
            str(kwargs.get("output_type", "AUTO") or "AUTO"),
            table_a,
            table_b,
        )
        out_path = _node_output_dir(self, context) / f"{Path(str(table_a)).stem}.merged{extension}"
        _write_table(out_path, output_fields, output_rows, output_delim)
        return (str(out_path),)

    @staticmethod
    def _resolve_join_keys(kwargs: dict[str, Any], fields_a: list[str], fields_b: list[str]) -> tuple[str, str]:
        shared_key = str(kwargs.get("join_key", "") or "").strip()
        key_a = str(kwargs.get("key_column_a", "") or "").strip() or shared_key
        key_b = str(kwargs.get("key_column_b", "") or "").strip() or key_a or shared_key
        if not key_a and not key_b:
            common = [field for field in fields_a if field in fields_b]
            if not common:
                raise ValueError("No common columns found. Please specify join_key or key_column_a/key_column_b.")
            key_a = key_b = common[0]
        elif key_a and not key_b:
            key_b = key_a
        elif key_b and not key_a:
            key_a = key_b
        if key_a not in fields_a:
            raise ValueError(f"Key column {key_a!r} must exist in table A")
        if key_b not in fields_b:
            raise ValueError(f"Key column {key_b!r} must exist in table B")
        return key_a, key_b

    @staticmethod
    def _output_format(output_type: str, table_a: str | Path, table_b: str | Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            inputs_are_csv = (
                Path(str(table_a)).suffix.lower() == ".csv"
                and Path(str(table_b)).suffix.lower() == ".csv"
            )
            return (",", ".csv") if inputs_are_csv else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")

    @staticmethod
    def _combine(
        left: dict[str, str],
        right: dict[str, str] | None,
        fields_a: list[str],
        right_output_names: dict[str, str],
    ) -> dict[str, str]:
        row = {field: left.get(field, "") for field in fields_a}
        for right_field, output_field in right_output_names.items():
            row[output_field] = right.get(right_field, "") if right else ""
        return row


class JoinTablesNode(BaseNode):
    """Join two CSV/TSV tables with multi-key and index join support."""

    NODE_ID = "join_tables"
    DISPLAY_NAME = "Join Tables"
    CATEGORY = "data_transform"
    DESCRIPTION = "Join two CSV/TSV tables with multi-key, suffix, and index-join options."
    SEARCH_ALIASES = ["join", "tables", "multi-key", "index join", "advanced join", "csv", "tsv"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("joined_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table_a": ("FILE", {"description": "Left CSV/TSV table"}),
                "table_b": ("FILE", {"description": "Right CSV/TSV table"}),
                "join_keys": ("STRING", {"default": "", "description": "Comma-separated join keys; empty joins by row index"}),
            },
            "optional": {
                "how": ("STRING", {"default": "inner", "options": ["inner", "left", "right", "outer"]}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "left_suffix": ("STRING", {"default": "_left", "advanced": True}),
                "right_suffix": ("STRING", {"default": "_right", "advanced": True}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table_a = kwargs["table_a"]
        table_b = kwargs["table_b"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table_a)
        fields_a, rows_a = _read_table(table_a, delim)
        fields_b, rows_b = _read_table(table_b, delim)
        join_keys = _split_csv(str(kwargs.get("join_keys", "")))
        how = str(kwargs.get("how", "inner") or "inner").lower()
        left_suffix = str(kwargs.get("left_suffix", "_left"))
        right_suffix = str(kwargs.get("right_suffix", "_right"))
        if how not in {"inner", "left", "right", "outer"}:
            raise ValueError(f"Unsupported join mode: {how}")

        output_fields = self._output_fields(fields_a, fields_b, join_keys, left_suffix, right_suffix)
        output_rows = (
            self._join_by_index(rows_a, rows_b, fields_a, fields_b, output_fields, how, left_suffix, right_suffix)
            if not join_keys
            else self._join_by_keys(rows_a, rows_b, fields_a, fields_b, output_fields, join_keys, how, left_suffix, right_suffix)
        )

        out_path = _node_output_dir(self, context) / "joined.tsv"
        _write_table(out_path, output_fields, output_rows, "\t")
        return (str(out_path),)

    @staticmethod
    def _output_fields(
        fields_a: list[str],
        fields_b: list[str],
        join_keys: list[str],
        left_suffix: str,
        right_suffix: str,
    ) -> list[str]:
        for key in join_keys:
            if key not in fields_a or key not in fields_b:
                raise ValueError(f"Join key {key!r} must exist in both tables")

        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        output_fields: list[str] = []
        for field in fields_a:
            output_fields.append(f"{field}{left_suffix}" if field in overlapping else field)
        for field in fields_b:
            if field in join_keys:
                continue
            output_fields.append(f"{field}{right_suffix}" if field in overlapping else field)
        return output_fields

    @classmethod
    def _join_by_keys(
        cls,
        rows_a: list[dict[str, str]],
        rows_b: list[dict[str, str]],
        fields_a: list[str],
        fields_b: list[str],
        output_fields: list[str],
        join_keys: list[str],
        how: str,
        left_suffix: str,
        right_suffix: str,
    ) -> list[dict[str, str]]:
        right_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows_b:
            right_by_key.setdefault(cls._key(row, join_keys), []).append(row)
        left_by_key: OrderedDict[tuple[str, ...], list[dict[str, str]]] = OrderedDict()
        for row in rows_a:
            left_by_key.setdefault(cls._key(row, join_keys), []).append(row)

        output_rows: list[dict[str, str]] = []
        if how in {"inner", "left", "outer"}:
            for left in rows_a:
                matches = right_by_key.get(cls._key(left, join_keys), [])
                if matches:
                    for right in matches:
                        output_rows.append(cls._combine(left, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
                elif how in {"left", "outer"}:
                    output_rows.append(cls._combine(left, None, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))

        if how in {"right", "outer"}:
            for right in rows_b:
                matches = left_by_key.get(cls._key(right, join_keys), [])
                if how == "right" and matches:
                    for left in matches:
                        output_rows.append(cls._combine(left, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
                elif not matches:
                    output_rows.append(cls._combine(None, right, fields_a, fields_b, join_keys, output_fields, left_suffix, right_suffix))
        return output_rows

    @classmethod
    def _join_by_index(
        cls,
        rows_a: list[dict[str, str]],
        rows_b: list[dict[str, str]],
        fields_a: list[str],
        fields_b: list[str],
        output_fields: list[str],
        how: str,
        left_suffix: str,
        right_suffix: str,
    ) -> list[dict[str, str]]:
        if how == "inner":
            indexes = range(min(len(rows_a), len(rows_b)))
        elif how == "left":
            indexes = range(len(rows_a))
        elif how == "right":
            indexes = range(len(rows_b))
        else:
            indexes = range(max(len(rows_a), len(rows_b)))
        return [
            cls._combine(
                rows_a[index] if index < len(rows_a) else None,
                rows_b[index] if index < len(rows_b) else None,
                fields_a,
                fields_b,
                [],
                output_fields,
                left_suffix,
                right_suffix,
            )
            for index in indexes
        ]

    @staticmethod
    def _key(row: dict[str, str], join_keys: list[str]) -> tuple[str, ...]:
        return tuple(row.get(key, "") for key in join_keys)

    @staticmethod
    def _combine(
        left: dict[str, str] | None,
        right: dict[str, str] | None,
        fields_a: list[str],
        fields_b: list[str],
        join_keys: list[str],
        output_fields: list[str],
        left_suffix: str,
        right_suffix: str,
    ) -> dict[str, str]:
        overlapping = (set(fields_a) & set(fields_b)) - set(join_keys)
        row = {field: "" for field in output_fields}
        for field in fields_a:
            out_field = f"{field}{left_suffix}" if field in overlapping else field
            row[out_field] = left.get(field, "") if left else right.get(field, "") if right and field in join_keys else ""
        for field in fields_b:
            if field in join_keys:
                if row.get(field, "") == "" and right:
                    row[field] = right.get(field, "")
                continue
            out_field = f"{field}{right_suffix}" if field in overlapping else field
            row[out_field] = right.get(field, "") if right else ""
        return row


class TSVToFastaNode(BaseNode):
    """Convert a delimited sequence table into FASTA records."""

    NODE_ID = "tsv_to_fasta"
    DISPLAY_NAME = "TSV to FASTA"
    CATEGORY = "data_transform"
    DESCRIPTION = "Convert a TSV or CSV table with sequence data to FASTA format."
    SEARCH_ALIASES = ["tsv", "csv", "fasta", "sequence", "convert", "table"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("fasta",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "TSV or CSV table with a header row"}),
                "id_column": ("STRING", {"description": "Column used for FASTA record IDs"}),
                "seq_column": ("STRING", {"description": "Column containing nucleotide or protein sequences"}),
            },
            "optional": {
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "line_width": (
                    "INT",
                    {"default": 80, "min": 0, "description": "FASTA line wrap width; 0 disables wrapping"},
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table = kwargs["table"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table)
        fieldnames, rows = _read_table(table, delim)
        id_column = str(kwargs["id_column"])
        seq_column = str(kwargs["seq_column"])
        missing = [column for column in (id_column, seq_column) if column not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")

        line_width = int(kwargs.get("line_width", 80))
        lines: list[str] = []
        for index, row in enumerate(rows, start=1):
            sequence = _fasta_sequence(row.get(seq_column, ""))
            if not sequence:
                raise ValueError(f"Row {index} has an empty sequence")
            lines.append(f">{_fasta_header(row.get(id_column, ''))}")
            lines.extend(_wrap_sequence(sequence, line_width))

        out_path = _node_output_dir(self, context) / f"{Path(str(table)).stem}.fasta"
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return (str(out_path),)


class AggregateByGroupNode(BaseNode):
    """Group a table and compute an aggregate value per group."""

    NODE_ID = "aggregate_by_group"
    DISPLAY_NAME = "Aggregate by Group"
    CATEGORY = "data_transform"
    DESCRIPTION = "Group rows by a column and compute count, sum, mean, min, or max."
    SEARCH_ALIASES = ["aggregate", "group", "summarize", "mean", "count", "table"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("aggregated_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "group_by": ("STRING", {"description": "Column used as the grouping key"}),
                "value_column": ("STRING", {"description": "Numeric column to aggregate"}),
                "operation": ("STRING", {"default": "mean", "options": ["count", "sum", "mean", "min", "max"]}),
            },
            "optional": {
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        table = kwargs["table"]
        delim = _delimiter(str(kwargs.get("delimiter", "auto")), table)
        fieldnames, rows = _read_table(table, delim)
        group_by = str(kwargs["group_by"])
        value_column = str(kwargs["value_column"])
        operation_name = str(kwargs.get("operation", "mean"))
        if group_by not in fieldnames:
            raise ValueError(f"Group column {group_by!r} not found")
        if operation_name != "count" and value_column not in fieldnames:
            raise ValueError(f"Value column {value_column!r} not found")

        groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
        for row in rows:
            groups.setdefault(row.get(group_by, ""), []).append(row)

        out_value = f"{operation_name}_{value_column or 'rows'}"
        output_rows: list[dict[str, Any]] = []
        for key, group_rows in groups.items():
            if operation_name == "count":
                value: float | int = len(group_rows)
            else:
                values = [_as_number(row.get(value_column, "")) for row in group_rows]
                if operation_name == "sum":
                    value = sum(values)
                elif operation_name == "mean":
                    value = sum(values) / len(values) if values else 0
                elif operation_name == "min":
                    value = min(values)
                elif operation_name == "max":
                    value = max(values)
                else:
                    raise ValueError(f"Unsupported operation: {operation_name}")
            output_rows.append({group_by: key, out_value: value})

        out_path = _node_output_dir(self, context) / "aggregated.tsv"
        _write_table(out_path, [group_by, out_value], output_rows, "	")
        return (str(out_path),)


class FormatConverterNode(BaseNode):
    """Convert table records in-process and bio formats with standard tools."""

    NODE_ID = "format_converter"
    DISPLAY_NAME = "Format Converter"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Convert table records between CSV, TSV, and JSON, or convert common "
        "bioinformatics formats with samtools, bcftools, gffread, and seqtk."
    )
    SEARCH_ALIASES = [
        "format",
        "convert",
        "converter",
        "csv",
        "tsv",
        "json",
        "table",
        "convert format",
        "bam to cram",
        "vcf to bcf",
        "gff to gtf",
        "fastq to fasta",
        "samtools convert",
        "bcftools convert",
        "file converter",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("converted_file",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["samtools", "bcftools", "gffread", "seqtk"]
    REQUIRED_CONDA_PACKAGES = ["samtools", "bcftools", "gffread", "seqtk"]

    _EXTENSIONS = {"csv": ".csv", "tsv": ".tsv", "json": ".json"}
    _TABLE_FORMATS = {"csv", "tsv", "json"}
    _ALIGNMENT_FORMATS = {"SAM", "BAM", "CRAM"}
    _VARIANT_FORMATS = {"VCF", "VCF_GZ", "BCF"}
    _ANNOTATION_FORMATS = {"GFF", "GTF"}
    _SEQUENCE_FORMATS = {"FASTQ", "FASTA"}
    _BIO_FORMATS = _ALIGNMENT_FORMATS | _VARIANT_FORMATS | _ANNOTATION_FORMATS | _SEQUENCE_FORMATS
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": (
                    "BAM,CRAM,SAM,VCF,VCF_GZ,BCF,GFF,GTF,FASTQ,FASTA,CSV,TSV,JSON",
                    {"description": "Input table or bioinformatics file"},
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "tsv",
                        "options": [
                            "csv",
                            "tsv",
                            "json",
                            "SAM",
                            "BAM",
                            "CRAM",
                            "VCF",
                            "VCF_GZ",
                            "BCF",
                            "GFF",
                            "GTF",
                            "FASTQ",
                            "FASTA",
                        ],
                    },
                ),
            },
            "optional": {
                "input_format": ("STRING", {"default": "auto", "options": ["auto", "csv", "tsv", "json"]}),
                "reference": (
                    "FASTA,FASTA_INDEX",
                    {"default": "", "description": "Reference FASTA required for CRAM output"},
                ),
                "compression_level": ("INT", {"default": 6, "min": 0, "max": 9}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
                "output_dir": ("STRING", {}),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation

        output_format_raw = str(inputs.get("output_format", "tsv"))
        output_format = cls._normalise_format_name(output_format_raw)
        if output_format in cls._TABLE_FORMATS:
            return True
        if output_format not in cls._BIO_FORMATS:
            return f"Unsupported output format: {output_format_raw}"

        input_format = cls._infer_bio_format(inputs.get("input_file", ""), inputs.get("input_format", "auto"))
        if input_format is None:
            return "Bio format conversion requires a recognised input file extension or input_format"
        if not cls._conversion_supported(input_format, output_format):
            return f"Cannot convert {input_format} to {output_format} with format_converter"
        if output_format == "CRAM" and not str(inputs.get("reference", "") or "").strip():
            return "reference is required for CRAM output"

        try:
            compression_level = int(inputs.get("compression_level", 6))
        except (TypeError, ValueError):
            return "compression_level must be an integer"
        if not 0 <= compression_level <= 9:
            return "compression_level must be between 0 and 9"

        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be at least 1"

        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_dir = Path(output_dir)
        node_out = output_dir / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        output_format = cls._normalise_format_name(str(inputs.get("output_format", "tsv")))
        return [node_out / cls._output_filename(inputs, output_format)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_format = cls._normalise_format_name(str(inputs.get("output_format", "tsv")))
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        input_file = str(inputs.get("input_file", ""))
        output_path = output / cls._output_filename(inputs, output_format)
        threads = str(int(inputs.get("threads", 1)))
        compression_level = str(int(inputs.get("compression_level", 6)))

        if output_format in cls._ALIGNMENT_FORMATS:
            cmd = ["samtools", "view", "-@", threads]
            if output_format == "BAM":
                cmd.extend(["-b", "-l", compression_level])
            elif output_format == "CRAM":
                cmd.extend(["-C", "-l", compression_level])
                reference = str(inputs.get("reference", "") or "").strip()
                if reference:
                    cmd.extend(["-T", reference])
            elif output_format == "SAM":
                cmd.append("-h")
            cmd.extend(["-o", str(output_path), input_file])
            return cmd

        if output_format in cls._VARIANT_FORMATS:
            out_flag = {"VCF": "-Ov", "VCF_GZ": "-Oz", "BCF": "-Ob"}[output_format]
            return [
                "bcftools",
                "view",
                "--threads",
                threads,
                out_flag,
                "-o",
                str(output_path),
                input_file,
            ]

        if output_format in cls._ANNOTATION_FORMATS:
            cmd = ["gffread", input_file]
            if output_format == "GTF":
                cmd.append("-T")
            cmd.extend(["-o", str(output_path)])
            return cmd

        if output_format in cls._SEQUENCE_FORMATS:
            cmd = ["seqtk", "seq"]
            if output_format == "FASTA":
                cmd.append("-A")
            cmd.extend([input_file, ">", str(output_path)])
            return cmd

        raise ValueError(f"Unsupported command output format: {output_format}")

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_file = Path(str(kwargs["input_file"]))
        output_format_raw = str(kwargs.get("output_format", "tsv"))
        output_format = self._normalise_format_name(output_format_raw)

        if output_format not in self._TABLE_FORMATS:
            output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
            output_path = self.PLAN_OUTPUTS(kwargs, output_dir)[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["output"] = str(output_path.parent)
            kwargs["output_dir"] = str(output_path.parent)
            validation = self.VALIDATE_INPUTS(kwargs)
            if validation is not True:
                raise ValueError(f"Input validation failed: {validation}")
            cmd = self.render_command(kwargs)
            rendered_cmd: str | list[str] = _shell_join(cmd) if self.SHELL else cmd
            if context is not None and hasattr(context, "run_command"):
                result = await context.run_command(rendered_cmd, cwd=output_dir)
            else:
                from bionodulo.execution.subprocess_runner import run_subprocess

                result = await run_subprocess(
                    rendered_cmd,
                    cwd=output_dir,
                    stdout_path=output_path.parent / "stdout.log",
                    stderr_path=output_path.parent / "stderr.log",
                )
            if result.get("returncode", 0) != 0:
                stderr = result.get("stderr", "")
                raise RuntimeError(f"Format conversion failed: {stderr[:500]}")
            return (str(output_path),)

        input_format = _normalise_table_format(str(kwargs.get("input_format", "auto")), input_file)
        records = _read_records(input_file, input_format)

        output_stem = str(kwargs.get("output_name", "") or "").strip() or input_file.stem
        output_name = f"{Path(output_stem).stem}{self._EXTENSIONS[output_format]}"
        output_path = _node_output_dir(self, context) / output_name
        _write_records(output_path, output_format, records)
        return (str(output_path),)

    @classmethod
    def _normalise_format_name(cls, value: str) -> str:
        cleaned = str(value or "").strip()
        lower = cleaned.lower()
        if lower in cls._TABLE_FORMATS:
            return lower
        return cleaned.upper()

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any], output_format: str) -> str:
        input_file = Path(str(inputs.get("input_file", cls.NODE_ID)))
        output_stem = str(inputs.get("output_name", "") or "").strip()
        if output_stem:
            stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(output_stem).stem).strip("._") or cls.NODE_ID
        else:
            stem = cls._clean_input_stem(input_file)
            if output_format not in cls._TABLE_FORMATS:
                stem = f"{stem}.to_{output_format.lower()}"
        extension = cls._EXTENSIONS.get(output_format, file_extension_for(output_format))
        return f"{stem}{extension}"

    @staticmethod
    def _clean_input_stem(path: Path) -> str:
        name = path.name
        for suffix in (".fastq.gz", ".fq.gz", ".vcf.gz", ".gff3.gz", ".gtf.gz"):
            if name.lower().endswith(suffix):
                return name[: -len(suffix)]
        stem = path.stem
        if stem.endswith(".vcf"):
            return stem[:-4]
        return stem

    @classmethod
    def _infer_bio_format(cls, input_file: Any, input_format: Any = "auto") -> str | None:
        requested = cls._normalise_format_name(str(input_format or "auto"))
        if requested != "AUTO" and requested not in cls._TABLE_FORMATS:
            return requested
        name = str(input_file or "").lower()
        if name.endswith((".sam", ".sam.gz")):
            return "SAM"
        if name.endswith((".bam", ".bam.gz")):
            return "BAM"
        if name.endswith((".cram", ".cram.gz")):
            return "CRAM"
        if name.endswith(".vcf.gz"):
            return "VCF_GZ"
        if name.endswith(".vcf"):
            return "VCF"
        if name.endswith(".bcf"):
            return "BCF"
        if name.endswith((".gff", ".gff3", ".gff.gz", ".gff3.gz")):
            return "GFF"
        if name.endswith((".gtf", ".gtf.gz")):
            return "GTF"
        if name.endswith((".fastq", ".fq", ".fastq.gz", ".fq.gz")):
            return "FASTQ"
        if name.endswith((".fasta", ".fa", ".fna", ".faa", ".fasta.gz", ".fa.gz", ".fna.gz", ".faa.gz")):
            return "FASTA"
        return None

    @classmethod
    def _conversion_supported(cls, input_format: str, output_format: str) -> bool:
        if input_format == output_format:
            return True
        groups = (
            cls._ALIGNMENT_FORMATS,
            cls._VARIANT_FORMATS,
            cls._ANNOTATION_FORMATS,
            cls._SEQUENCE_FORMATS,
        )
        return any(input_format in group and output_format in group for group in groups)


class SetFieldsNode(BaseNode):
    """Add or update table fields using constant values or row templates."""

    NODE_ID = "set_fields"
    DISPLAY_NAME = "Set Fields"
    CATEGORY = "data_transform"
    DESCRIPTION = "Add, update, or keep selected CSV/TSV fields using JSON field assignments."
    SEARCH_ALIASES = [
        "set",
        "fields",
        "field mapping",
        "assign",
        "update columns",
        "add columns",
        "data mapping",
        "table transform",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("updated_table",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "assignments": (
                    "STRING",
                    {
                        "default": "{}",
                        "multiline": True,
                        "description": 'JSON object mapping output fields to constants or "{column}" templates',
                    },
                ),
            },
            "optional": {
                "keep_only_set": (
                    "BOOLEAN",
                    {"default": False, "description": "Only emit fields listed in assignments or field_order"},
                ),
                "field_order": (
                    "STRING",
                    {"default": "", "description": "Comma-separated output field order override"},
                ),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delim = _delimiter(str(kwargs.get("delimiter", "auto")), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        assignments = self._parse_assignments(str(kwargs.get("assignments", "{}") or "{}"))
        if not assignments:
            raise ValueError("assignments must include at least one field")

        updated_rows = [
            self._apply_assignments(row, assignments)
            for row in rows
        ]
        output_fields = self._output_fields(
            fieldnames,
            assignments,
            str(kwargs.get("field_order", "") or ""),
            bool(kwargs.get("keep_only_set", False)),
        )
        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        output_path = _node_output_dir(self, context) / f"{input_path.stem}.set{extension}"
        _write_table(output_path, output_fields, updated_rows, output_delim)
        return (str(output_path),)

    @staticmethod
    def _parse_assignments(value: str) -> OrderedDict[str, Any]:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"assignments must be a JSON object: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("assignments must be a JSON object")
        assignments: OrderedDict[str, Any] = OrderedDict()
        for key, assigned_value in parsed.items():
            field = str(key).strip()
            if not field:
                raise ValueError("assignment field names must be non-empty")
            assignments[field] = assigned_value
        return assignments

    @classmethod
    def _apply_assignments(cls, row: dict[str, str], assignments: OrderedDict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = dict(row)
        for field, value in assignments.items():
            output[field] = cls._render_value(value, row)
        return output

    @staticmethod
    def _render_value(value: Any, row: dict[str, str]) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return value.format_map(row)
        except KeyError as exc:
            missing = str(exc.args[0])
            raise ValueError(f"Unknown template field: {missing}") from exc

    @staticmethod
    def _output_fields(
        fieldnames: list[str],
        assignments: OrderedDict[str, Any],
        field_order: str,
        keep_only_set: bool,
    ) -> list[str]:
        explicit_order = _split_csv(field_order)
        if explicit_order:
            unknown = [field for field in explicit_order if field not in fieldnames and field not in assignments]
            if unknown:
                raise ValueError(f"field_order includes unknown field(s): {', '.join(unknown)}")
            return explicit_order
        if keep_only_set:
            return list(assignments.keys())
        output_fields = list(fieldnames)
        output_fields.extend(field for field in assignments if field not in fieldnames)
        return output_fields

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


class TransposeTableNode(BaseNode):
    """Transpose rows and columns of a CSV/TSV table."""

    NODE_ID = "transpose_table"
    DISPLAY_NAME = "Transpose Table"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Transpose rows and columns of a table. The first column, or specified ID column, "
        "becomes the new header row."
    )
    SEARCH_ALIASES = [
        "transpose",
        "pivot",
        "flip",
        "rotate",
        "swap axes",
        "expression matrix transpose",
        "count table transpose",
        "genes as rows",
        "samples as columns",
    ]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("transposed_table",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
            },
            "optional": {
                "id_column": ("STRING", {"default": "", "description": "Column to use as transposed header IDs"}),
                "new_header": ("STRING", {"default": "", "description": "Name for the new index column"}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delim = _delimiter(str(kwargs.get("delimiter", "auto")), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        id_column = str(kwargs.get("id_column", "") or fieldnames[0])
        if id_column not in fieldnames:
            raise ValueError(f"ID column {id_column!r} not found")

        output_ids = [row.get(id_column, "") for row in rows]
        duplicate_ids = sorted({value for value in output_ids if output_ids.count(value) > 1})
        if duplicate_ids:
            raise ValueError(f"ID column contains duplicate values: {', '.join(duplicate_ids)}")

        index_header = str(kwargs.get("new_header", "") or id_column)
        value_columns = [name for name in fieldnames if name != id_column]
        output_fields = [index_header] + output_ids
        output_rows = [
            {index_header: column, **{row.get(id_column, ""): row.get(column, "") for row in rows}}
            for column in value_columns
        ]

        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        output_path = _node_output_dir(self, context) / f"{input_path.stem}.transposed{extension}"
        _write_table(output_path, output_fields, output_rows, output_delim)
        return (str(output_path),)

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


class ReplaceTextNode(BaseNode):
    """Find and replace text in text-based files."""

    NODE_ID = "replace_text"
    DISPLAY_NAME = "Replace Text"
    CATEGORY = "data_transform"
    DESCRIPTION = "Find and replace text in text-based files using literal or regex matching."
    SEARCH_ALIASES = ["replace", "find and replace", "sed", "regex replace", "text substitution", "pattern replace"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("replaced_file",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Text-based input file"}),
                "search": ("STRING", {"default": "", "description": "Literal text or regex pattern to find"}),
                "replace": ("STRING", {"default": "", "description": "Replacement text"}),
            },
            "optional": {
                "use_regex": ("BOOLEAN", {"default": False}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
                "whole_word": ("BOOLEAN", {"default": False}),
                "limit_per_line": ("INT", {"default": 0, "min": 0, "max": 9999}),
                "affected_lines_only": ("BOOLEAN", {"default": False}),
                "output_extension": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["file"]))
        search = str(kwargs.get("search", ""))
        replacement = str(kwargs.get("replace", ""))
        use_regex = bool(kwargs.get("use_regex", False))
        case_sensitive = bool(kwargs.get("case_sensitive", True))
        whole_word = bool(kwargs.get("whole_word", False))
        limit_per_line = max(0, int(kwargs.get("limit_per_line", 0) or 0))
        affected_lines_only = bool(kwargs.get("affected_lines_only", False))
        output_extension = str(kwargs.get("output_extension", "") or "")

        if search == "":
            raise ValueError("search must not be empty")

        pattern = search if use_regex else re.escape(search)
        if whole_word:
            pattern = rf"\b{pattern}\b"
        flags = 0 if case_sensitive else re.IGNORECASE
        compiled = re.compile(pattern, flags)

        extension = output_extension if output_extension else input_path.suffix
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        output_name = f"{input_path.stem}.replaced{extension}"
        out_path = _node_output_dir(self, context) / output_name

        with input_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
            for line in fin:
                new_line, count = compiled.subn(replacement, line, count=limit_per_line)
                if affected_lines_only:
                    if count:
                        fout.write(new_line)
                else:
                    fout.write(new_line)

        return (str(out_path),)


class SortFileNode(BaseNode):
    """Sort delimited text files by named columns or zero-based column indices."""

    NODE_ID = "sort_file"
    DISPLAY_NAME = "Sort File"
    CATEGORY = "data_transform"
    DESCRIPTION = "Sort a delimited table by one or more columns using numeric, string, or automatic comparison."
    SEARCH_ALIASES = ["sort", "order", "reorder", "ascending", "descending", "numeric sort", "table sort"]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("sorted_file",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Delimited text file to sort"}),
                "sort_column": ("STRING", {"default": "", "description": "Column name or 0-based index; comma-separated"}),
            },
            "optional": {
                "sort_type": ("STRING", {"default": "auto", "options": ["auto", "string", "numeric"]}),
                "ascending": ("BOOLEAN", {"default": True}),
                "stable": ("BOOLEAN", {"default": True}),
                "has_header": ("BOOLEAN", {"default": True}),
                "separator": ("STRING", {"default": "auto", "options": ["auto", "comma", "tab", "space"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["file"]))
        sort_column = str(kwargs.get("sort_column", "") or "")
        sort_type = str(kwargs.get("sort_type", "auto") or "auto").lower()
        ascending = bool(kwargs.get("ascending", True))
        has_header = bool(kwargs.get("has_header", True))
        separator = self._separator(str(kwargs.get("separator", "auto") or "auto"), input_path)
        output_type = str(kwargs.get("output_type", "AUTO") or "AUTO").upper()
        if sort_type not in {"auto", "string", "numeric"}:
            raise ValueError(f"Unsupported sort_type: {sort_type}")

        rows = self._read_rows(input_path, separator)
        header: list[str] | None = rows[0] if has_header and rows else None
        data_rows = rows[1:] if header else rows
        sort_indexes = self._sort_indexes(sort_column, header, data_rows)
        sorted_rows = sorted(
            data_rows,
            key=lambda row: self._sort_key(row, sort_indexes, sort_type),
            reverse=not ascending,
        )

        output_sep, extension = self._output_format(output_type, input_path)
        output_path = _node_output_dir(self, context) / f"{input_path.stem}.sorted{extension}"
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, delimiter=output_sep, lineterminator="\n")
            if header:
                writer.writerow(header)
            writer.writerows(sorted_rows)
        return (str(output_path),)

    @staticmethod
    def _separator(separator: str, path: Path) -> str:
        mode = separator.lower()
        if mode == "comma":
            return ","
        if mode == "tab":
            return "\t"
        if mode == "space":
            return " "
        if mode == "auto":
            return "," if path.suffix.lower() == ".csv" else "\t"
        raise ValueError(f"Unsupported separator: {separator}")

    @staticmethod
    def _read_rows(path: Path, separator: str) -> list[list[str]]:
        with path.open(newline="", encoding="utf-8") as fh:
            return [row for row in csv.reader(fh, delimiter=separator)]

    @staticmethod
    def _sort_indexes(sort_column: str, header: list[str] | None, rows: list[list[str]]) -> list[int]:
        width = max((len(row) for row in rows), default=len(header or []))
        if not sort_column.strip():
            return list(range(width))
        indexes: list[int] = []
        for item in _split_csv(sort_column):
            if header is not None and not item.isdigit():
                if item not in header:
                    raise ValueError(f"Sort column {item!r} not found")
                indexes.append(header.index(item))
            else:
                index = int(item)
                if index < 0:
                    raise ValueError(f"Sort column index must be non-negative: {item}")
                indexes.append(index)
        return indexes

    @classmethod
    def _sort_key(cls, row: list[str], indexes: list[int], sort_type: str) -> tuple[Any, ...]:
        return tuple(cls._coerce_sort_value(row[index] if index < len(row) else "", sort_type) for index in indexes)

    @staticmethod
    def _coerce_sort_value(value: str, sort_type: str) -> Any:
        if sort_type == "string":
            return str(value)
        if sort_type == "numeric":
            try:
                return (0, _as_number(value))
            except ValueError:
                return (1, str(value))
        try:
            return (0, _as_number(value))
        except ValueError:
            return (1, str(value))

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        if output_type == "CSV":
            return ",", ".csv"
        if output_type == "TSV":
            return "\t", ".tsv"
        if output_type == "AUTO":
            return (",", ".csv") if input_path.suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")


class DeduplicateNode(BaseNode):
    """Remove duplicate rows from CSV/TSV tables or duplicate FASTA sequences."""

    NODE_ID = "deduplicate"
    DISPLAY_NAME = "Deduplicate"
    CATEGORY = "data_transform"
    DESCRIPTION = "Remove duplicate table rows or FASTA records based on selected key columns or sequence content."
    SEARCH_ALIASES = [
        "deduplicate",
        "remove duplicates",
        "unique",
        "distinct",
        "drop duplicates",
        "dedup",
        "unique rows",
        "fasta dedup",
        "sequence dedup",
    ]
    RETURN_TYPES = ("CSV", "CSV")
    RETURN_NAMES = ("deduplicated", "duplicates")
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "subset_columns": ("STRING", {"default": "", "description": "Comma-separated duplicate key columns"}),
            },
            "optional": {
                "keep": ("STRING", {"default": "first", "options": ["first", "last", "none"]}),
                "report_dups": ("BOOLEAN", {"default": False}),
                "sort_before": ("BOOLEAN", {"default": False}),
                "delimiter": ("STRING", {"default": "auto", "options": ["auto", "tsv", "csv"]}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        keep = str(kwargs.get("keep", "first") or "first").lower()
        if keep not in {"first", "last", "none"}:
            raise ValueError(f"Unsupported keep strategy: {keep}")
        if self._is_fasta(input_path):
            return self._deduplicate_fasta(
                input_path,
                keep,
                bool(kwargs.get("report_dups", False)),
                context,
            )

        input_delim = _delimiter(str(kwargs.get("delimiter", "auto")), input_path)
        fieldnames, rows = _read_table(input_path, input_delim)
        subset_columns = _split_csv(str(kwargs.get("subset_columns", "")))
        key_columns = subset_columns or list(fieldnames)
        missing = [name for name in key_columns if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")

        working_rows = list(rows)
        if bool(kwargs.get("sort_before", False)):
            working_rows.sort(key=lambda row: tuple(row.get(name, "") for name in fieldnames))

        deduplicated, duplicates = self._deduplicate_rows(working_rows, key_columns, keep)
        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        output_dir = _node_output_dir(self, context)
        deduplicated_path = output_dir / f"{input_path.stem}.deduplicated{extension}"
        duplicates_path = output_dir / f"{input_path.stem}.duplicates{extension}"

        _write_table(deduplicated_path, fieldnames, deduplicated, output_delim)
        if bool(kwargs.get("report_dups", False)):
            _write_table(duplicates_path, fieldnames, duplicates, output_delim)
        else:
            duplicates_path = deduplicated_path
        return (str(deduplicated_path), str(duplicates_path))

    @staticmethod
    def _row_key(row: dict[str, str], key_columns: list[str]) -> tuple[str, ...]:
        return tuple(row.get(column, "") for column in key_columns)

    @classmethod
    def _deduplicate_rows(
        cls,
        rows: list[dict[str, str]],
        key_columns: list[str],
        keep: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        if keep == "none":
            counts: OrderedDict[tuple[str, ...], int] = OrderedDict()
            for row in rows:
                key = cls._row_key(row, key_columns)
                counts[key] = counts.get(key, 0) + 1
            return (
                [row for row in rows if counts[cls._row_key(row, key_columns)] == 1],
                [row for row in rows if counts[cls._row_key(row, key_columns)] > 1],
            )

        keep_indexes: set[int] = set()
        duplicate_indexes: set[int] = set()
        seen: dict[tuple[str, ...], int] = {}
        row_range = range(len(rows)) if keep == "first" else range(len(rows) - 1, -1, -1)
        for index in row_range:
            key = cls._row_key(rows[index], key_columns)
            if key in seen:
                duplicate_indexes.add(index)
            else:
                seen[key] = index
                keep_indexes.add(index)

        return (
            [row for index, row in enumerate(rows) if index in keep_indexes],
            [row for index, row in enumerate(rows) if index in duplicate_indexes],
        )

    @classmethod
    def _deduplicate_fasta(cls, input_path: Path, keep: str, report_dups: bool, context: Any) -> tuple[str, str]:
        records = cls._read_fasta(input_path)
        kept, duplicates = cls._deduplicate_fasta_records(records, keep)
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        output_dir = base / cls.NODE_ID
        output_dir.mkdir(parents=True, exist_ok=True)
        deduplicated_path = output_dir / f"{input_path.stem}.deduplicated.fasta"
        duplicates_path = output_dir / f"{input_path.stem}.duplicates.fasta"

        cls._write_fasta(deduplicated_path, kept)
        if report_dups:
            cls._write_fasta(duplicates_path, duplicates)
        else:
            duplicates_path = deduplicated_path
        return (str(deduplicated_path), str(duplicates_path))

    @staticmethod
    def _is_fasta(path: Path) -> bool:
        return "".join(path.suffixes).lower() in {
            ".fa",
            ".fna",
            ".faa",
            ".fasta",
        }

    @staticmethod
    def _read_fasta(path: Path) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        header = ""
        seq_parts: list[str] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    records.append((header, "".join(seq_parts).upper()))
                header = line
                seq_parts = []
            else:
                seq_parts.append(line)
        if header:
            records.append((header, "".join(seq_parts).upper()))
        if not records:
            raise ValueError(f"FASTA file has no records: {path}")
        return records

    @classmethod
    def _deduplicate_fasta_records(
        cls,
        records: list[tuple[str, str]],
        keep: str,
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
        if keep == "none":
            counts: OrderedDict[str, int] = OrderedDict()
            for _header, sequence in records:
                counts[sequence] = counts.get(sequence, 0) + 1
            return (
                [record for record in records if counts[record[1]] == 1],
                [record for record in records if counts[record[1]] > 1],
            )

        kept_indexes: set[int] = set()
        duplicate_indexes: set[int] = set()
        seen: set[str] = set()
        row_range = range(len(records)) if keep == "first" else range(len(records) - 1, -1, -1)
        for index in row_range:
            sequence = records[index][1]
            if sequence in seen:
                duplicate_indexes.add(index)
            else:
                seen.add(sequence)
                kept_indexes.add(index)
        return (
            [record for index, record in enumerate(records) if index in kept_indexes],
            [record for index, record in enumerate(records) if index in duplicate_indexes],
        )

    @staticmethod
    def _write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for header, sequence in records:
                fh.write(f"{header}\n")
                for line in _wrap_sequence(sequence, 60):
                    fh.write(f"{line}\n")

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


class StringFormatNode(BaseNode):
    """Render a format string from JSON variables."""

    NODE_ID = "string_format"
    DISPLAY_NAME = "String Format"
    CATEGORY = "primitive"
    DESCRIPTION = "Render a Python format-string style template using values from a JSON object."
    SEARCH_ALIASES = ["string", "format", "template", "text", "primitive"]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "description": "Template such as sample {sample}"}),
            },
            "optional": {
                "variables_json": ("STRING", {"default": "{}", "multiline": True, "description": "JSON object of template variables"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        kwargs.pop("context", None)
        template = str(kwargs.get("template", ""))
        variables = json.loads(str(kwargs.get("variables_json", "{}") or "{}"))
        if not isinstance(variables, dict):
            raise ValueError("variables_json must be a JSON object")
        return (template.format(**variables),)


class MathExpressionNode(BaseNode):
    """Evaluate a safe numeric expression with JSON variables."""

    NODE_ID = "math_expression"
    DISPLAY_NAME = "Math Expression"
    CATEGORY = "primitive"
    DESCRIPTION = "Evaluate a safe numeric expression and emit float, int, boolean, and string forms."
    SEARCH_ALIASES = ["math", "expression", "calculate", "primitive", "number"]
    RETURN_TYPES = ("FLOAT", "INT", "BOOLEAN", "STRING")
    RETURN_NAMES = ("float_result", "int_result", "boolean_result", "string_result")
    REQUIRES_EXTERNAL_TOOLS = False

    _BINARY_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
        ast.UAdd: lambda value: value,
        ast.USub: operator.neg,
    }
    _FUNCTIONS: dict[str, Callable[..., float]] = {
        "abs": abs,
        "ceil": math.ceil,
        "floor": math.floor,
        "log": math.log,
        "max": max,
        "min": min,
        "round": round,
        "sqrt": math.sqrt,
    }

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "expression": ("STRING", {"description": "Numeric expression using variables, e.g. a * 2 + b"}),
            },
            "optional": {
                "variables_json": ("STRING", {"default": "{}", "multiline": True, "description": "JSON object of numeric variables"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int, bool, str]:
        kwargs.pop("context", None)
        expression = str(kwargs.get("expression", ""))
        variables = json.loads(str(kwargs.get("variables_json", "{}") or "{}"))
        if not isinstance(variables, dict):
            raise ValueError("variables_json must be a JSON object")
        numeric_vars = {str(key): _as_number(value) for key, value in variables.items()}
        tree = ast.parse(expression, mode="eval")
        value = float(self._eval(tree.body, numeric_vars))
        return (value, int(value), bool(value), _format_scalar(value))

    @classmethod
    def _eval(cls, node: ast.AST, variables: dict[str, float]) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            raise ValueError("Math expressions only support numeric constants")
        if isinstance(node, ast.Name):
            if node.id not in variables:
                raise ValueError(f"Unknown variable: {node.id}")
            return variables[node.id]
        if isinstance(node, ast.BinOp):
            op = cls._BINARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return float(op(cls._eval(node.left, variables), cls._eval(node.right, variables)))
        if isinstance(node, ast.UnaryOp):
            op = cls._UNARY_OPS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return float(op(cls._eval(node.operand, variables)))
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in cls._FUNCTIONS:
                raise ValueError("Only approved math functions are supported")
            args = [cls._eval(arg, variables) for arg in node.args]
            return float(cls._FUNCTIONS[node.func.id](*args))
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")

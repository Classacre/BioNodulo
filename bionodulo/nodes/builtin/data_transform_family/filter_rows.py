"""Deterministic CSV/TSV row filtering with Python 3.12 semantics."""

from __future__ import annotations

import operator
import re
from pathlib import Path
from typing import Any, Callable

from .adapter import (
    DELIMITER_MODES,
    OUTPUT_TYPES,
    PythonDataTransformNode,
    as_number,
    delimiter_for,
    node_output_dir,
    output_delimiter_and_extension,
    path_value,
    read_table,
    split_fields,
    validate_choice,
    write_table,
)


FILTER_OPERATORS = (
    "equals",
    "not_equals",
    "==",
    "!=",
    "contains",
    "not_contains",
    "startswith",
    "endswith",
    "regex",
    "greater_than",
    ">",
    "greater_or_equal",
    ">=",
    "less_than",
    "<",
    "less_or_equal",
    "<=",
    "in",
    "not_in",
    "is_empty",
    "is_not_empty",
    "is_null",
    "is_not_null",
)
NUMERIC_OPERATORS = frozenset({"greater_than", "greater_or_equal", "less_than", "less_or_equal"})


class FilterRowsNode(PythonDataTransformNode):
    """Filter table rows using one or two explicit predicates."""

    NODE_ID = "filter_rows"
    DISPLAY_NAME = "Filter Rows"
    DESCRIPTION = "Filter CSV/TSV rows using string, numeric, regex, membership, or emptiness predicates."
    SEARCH_ALIASES = [
        "filter",
        "rows",
        "table",
        "csv",
        "tsv",
        "subset rows",
        "where",
        "query",
        "conditional filter",
        "table filter",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("filtered_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/re.html"
    UPSTREAM_SOURCE = "Lib/csv.py; Lib/re; built-in string and float comparisons"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, invalid predicates, regex errors, and invalid numeric comparison "
        "values are fatal; non-numeric cells simply do not satisfy numeric predicates."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "column": ("STRING", {"description": "Column to test"}),
                "operator": (list(FILTER_OPERATORS), {"default": "equals"}),
                "value": ("STRING", {"default": "", "description": "Comparison value"}),
            },
            "optional": {
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
                "case_sensitive": ("BOOLEAN", {"default": True}),
                "invert": ("BOOLEAN", {"default": False}),
                "logical_op": (["AND", "OR"], {"default": "AND"}),
                "column_2": ("STRING", {"default": ""}),
                "operator_2": (["", *FILTER_OPERATORS], {"default": ""}),
                "value_2": ("STRING", {"default": ""}),
                "output_type": (list(OUTPUT_TYPES), {"default": "AUTO"}),
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
        if not str(inputs.get("column", "")).strip():
            return "Input 'column' must be non-empty"
        validation = validate_choice(inputs.get("operator", "equals"), "operator", FILTER_OPERATORS)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("output_type", "AUTO"), "output_type", OUTPUT_TYPES)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("logical_op", "AND"), "logical_op", ("AND", "OR"))
        if validation is not True:
            return validation
        operator_2 = str(inputs.get("operator_2", "") or "")
        if operator_2:
            validation = validate_choice(operator_2, "operator_2", FILTER_OPERATORS)
            if validation is not True:
                return validation
            if not str(inputs.get("column_2", "")).strip():
                return "Input 'column_2' is required when 'operator_2' is set"
        for operator_key, value_key in (("operator", "value"), ("operator_2", "value_2")):
            operator_name = cls.normalize_operator(str(inputs.get(operator_key, "") or ""))
            if operator_name in NUMERIC_OPERATORS:
                try:
                    as_number(inputs.get(value_key, ""))
                except (TypeError, ValueError):
                    return f"Input '{value_key}' must be a finite number for {operator_name}"
        return True

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        table = Path(path_value(kwargs["table"])).expanduser()
        delimiter = delimiter_for(kwargs.get("delimiter", "auto"), table)
        fieldnames, rows = read_table(table, delimiter)
        column = str(kwargs["column"]).strip()
        if column not in fieldnames:
            raise ValueError(f"Column {column!r} not found in table")
        column_2 = str(kwargs.get("column_2", "") or "").strip()
        operator_2 = str(kwargs.get("operator_2", "") or "")
        if operator_2 and column_2 not in fieldnames:
            raise ValueError(f"Column {column_2!r} not found in table")

        logical_op = str(kwargs.get("logical_op", "AND") or "AND")
        case_sensitive = bool(kwargs.get("case_sensitive", True))
        invert = bool(kwargs.get("invert", False))
        filtered: list[dict[str, str]] = []
        for row in rows:
            passed = self.matches(
                row.get(column, ""),
                str(kwargs.get("operator", "equals")),
                str(kwargs.get("value", "")),
                case_sensitive,
            )
            if operator_2:
                second = self.matches(
                    row.get(column_2, ""),
                    operator_2,
                    str(kwargs.get("value_2", "")),
                    case_sensitive,
                )
                passed = passed and second if logical_op == "AND" else passed or second
            if invert:
                passed = not passed
            if passed:
                filtered.append(row)

        output_delimiter, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), table)
        output_path = node_output_dir(self, context) / f"{table.stem}.filtered{extension}"
        write_table(output_path, fieldnames, filtered, output_delimiter)
        return (str(output_path),)

    @staticmethod
    def normalize_operator(operator_name: str) -> str:
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
        normalized = operator_name.strip()
        return aliases.get(normalized, normalized)

    @classmethod
    def matches(
        cls,
        actual: str,
        operator_name: str,
        expected: str,
        case_sensitive: bool,
    ) -> bool:
        operator_name = cls.normalize_operator(operator_name)
        text = str(actual or "")
        compare_to = str(expected or "")
        text_cmp = text if case_sensitive else text.casefold()
        expected_cmp = compare_to if case_sensitive else compare_to.casefold()
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
        if operator_name == "is_empty":
            return not text.strip()
        if operator_name == "is_not_empty":
            return bool(text.strip())
        if operator_name in {"in", "not_in"}:
            members = split_fields(expected_cmp)
            present = text_cmp in members
            return present if operator_name == "in" else not present

        comparisons: dict[str, Callable[[float, float], bool]] = {
            "greater_than": operator.gt,
            "greater_or_equal": operator.ge,
            "less_than": operator.lt,
            "less_or_equal": operator.le,
        }
        if operator_name in comparisons:
            try:
                return comparisons[operator_name](as_number(text), as_number(compare_to))
            except (TypeError, ValueError):
                return False
        raise ValueError(f"Unsupported filter operator: {operator_name}")

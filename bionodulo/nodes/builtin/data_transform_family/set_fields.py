"""Constant and direct-placeholder field assignment for CSV/TSV tables."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from string import Formatter
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    OUTPUT_TYPES,
    PythonDataTransformNode,
    delimiter_for,
    node_output_dir,
    output_delimiter_and_extension,
    path_value,
    read_table,
    split_fields,
    validate_choice,
    write_table,
)


class SetFieldsNode(PythonDataTransformNode):
    """Add or update table fields with JSON constants or direct row placeholders."""

    NODE_ID = "set_fields"
    DISPLAY_NAME = "Set Fields"
    DESCRIPTION = "Add or update CSV/TSV fields using JSON constants or direct {column} placeholders."
    SEARCH_ALIASES = ["set", "fields", "field mapping", "assign", "update columns", "add columns"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("updated_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/string.html"
    UPSTREAM_SOURCE = "Lib/string.py Formatter.parse; Lib/json; Lib/csv.py"
    PRODUCT_ORIGIN_COMMIT = "23cb7d94dd34b0735340d4a758dd89063fe2618a"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables or JSON, empty assignments, unknown placeholders, formatting "
        "directives, unknown field-order entries, and duplicate output fields are fatal."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "assignments": (
                    "STRING",
                    {"default": "{}", "multiline": True, "description": "JSON field-to-value mapping"},
                ),
            },
            "optional": {
                "keep_only_set": ("BOOLEAN", {"default": False}),
                "field_order": ("STRING", {"default": ""}),
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
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
        validation = validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("output_type", "AUTO"), "output_type", OUTPUT_TYPES)

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
        assignments = self.parse_assignments(str(kwargs.get("assignments", "{}") or "{}"))
        if not assignments:
            raise ValueError("assignments must include at least one field")
        updated_rows = [self.apply_assignments(row, assignments) for row in rows]
        output_fields = self.output_fields(
            fieldnames,
            assignments,
            str(kwargs.get("field_order", "") or ""),
            bool(kwargs.get("keep_only_set", False)),
        )
        if len(output_fields) != len(set(output_fields)):
            raise ValueError("Output field names must be unique")
        output_delimiter, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), table)
        output_path = node_output_dir(self, context) / f"{table.stem}.set{extension}"
        write_table(output_path, output_fields, updated_rows, output_delimiter)
        return (str(output_path),)

    @staticmethod
    def parse_assignments(value: str) -> OrderedDict[str, Any]:
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
    def apply_assignments(cls, row: dict[str, str], assignments: OrderedDict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = dict(row)
        for field, value in assignments.items():
            output[field] = cls.render_value(value, row)
        return output

    @staticmethod
    def render_value(value: Any, row: dict[str, str]) -> Any:
        if not isinstance(value, str):
            return value
        parts: list[str] = []
        for literal, field_name, format_spec, conversion in Formatter().parse(value):
            parts.append(literal)
            if field_name is None:
                continue
            if format_spec or conversion:
                raise ValueError("Assignment templates only support direct {column} placeholders")
            if field_name not in row:
                raise ValueError(f"Unknown template field: {field_name}")
            parts.append(row[field_name])
        return "".join(parts)

    @staticmethod
    def output_fields(
        fieldnames: list[str],
        assignments: OrderedDict[str, Any],
        field_order: str,
        keep_only_set: bool,
    ) -> list[str]:
        explicit = split_fields(field_order)
        if explicit:
            unknown = [name for name in explicit if name not in fieldnames and name not in assignments]
            if unknown:
                raise ValueError(f"field_order includes unknown field(s): {', '.join(unknown)}")
            return explicit
        if keep_only_set:
            return list(assignments)
        return [*fieldnames, *(name for name in assignments if name not in fieldnames)]

"""Column selection, ordering, and renaming for strict CSV/TSV tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    OUTPUT_TYPES,
    PythonDataTransformNode,
    delimiter_for,
    node_output_dir,
    output_delimiter_and_extension,
    parse_rename_map,
    path_value,
    read_table,
    split_fields,
    validate_choice,
    write_table,
)


class ExtractColumnsNode(PythonDataTransformNode):
    """Select, reorder, drop, and rename table columns."""

    NODE_ID = "extract_columns"
    DISPLAY_NAME = "Extract Columns"
    DESCRIPTION = "Select, reorder, drop, and optionally rename columns from a CSV/TSV table."
    SEARCH_ALIASES = ["columns", "select", "rename", "drop columns", "table", "csv", "tsv"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("extracted_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; ordered dict insertion semantics"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, missing or duplicate columns, invalid indices, and ambiguous renames "
        "are fatal; output column order is deterministic."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "columns": (
                    "STRING",
                    {"default": "", "description": "Comma-separated columns, '*', or ':N'"},
                ),
            },
            "optional": {
                "column_indices": (
                    "STRING",
                    {"default": "", "description": "Comma-separated zero-based column indices"},
                ),
                "rename_map": ("STRING", {"default": "", "description": "old:new pairs"}),
                "rename_to": ("STRING", {"default": "", "description": "Positional output names"}),
                "drop_mode": ("BOOLEAN", {"default": False}),
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
        if not str(inputs.get("columns", "")).strip() and not str(inputs.get("column_indices", "")).strip():
            return "Input 'columns' or 'column_indices' must select at least one column"
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
        delimiter = delimiter_for(kwargs.get("delimiter", "auto"), table)
        fieldnames, rows = read_table(table, delimiter)
        selected = self.selected_columns(
            fieldnames,
            str(kwargs.get("columns", "") or ""),
            str(kwargs.get("column_indices", "") or ""),
        )
        missing = [name for name in selected if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")
        if len(selected) != len(set(selected)):
            raise ValueError("Selected columns must be unique")
        if bool(kwargs.get("drop_mode", False)):
            selected_set = set(selected)
            selected = [name for name in fieldnames if name not in selected_set]
        if not selected:
            raise ValueError("Column selection cannot produce an empty table")

        rename_map = parse_rename_map(kwargs.get("rename_map", ""))
        unknown_renames = [name for name in rename_map if name not in selected]
        if unknown_renames:
            raise ValueError(f"Rename source column(s) not selected: {', '.join(unknown_renames)}")
        output_fields = self.output_fields(
            selected,
            rename_map,
            str(kwargs.get("rename_to", "") or ""),
        )
        if len(output_fields) != len(set(output_fields)):
            raise ValueError("Output column names must be unique")
        output_rows = [
            {
                output_name: row.get(source_name, "")
                for source_name, output_name in zip(selected, output_fields, strict=True)
            }
            for row in rows
        ]
        output_delimiter, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), table)
        output_path = node_output_dir(self, context) / f"{table.stem}.extracted{extension}"
        write_table(output_path, output_fields, output_rows, output_delimiter)
        return (str(output_path),)

    @staticmethod
    def selected_columns(fieldnames: list[str], columns: str, column_indices: str) -> list[str]:
        if column_indices.strip():
            selected: list[str] = []
            for item in split_fields(column_indices):
                try:
                    index = int(item)
                except ValueError as exc:
                    raise ValueError(f"Column index must be an integer: {item}") from exc
                if not 0 <= index < len(fieldnames):
                    raise ValueError(f"Column index out of range: {index}")
                selected.append(fieldnames[index])
            return selected
        expression = columns.strip()
        if expression == "*":
            return list(fieldnames)
        if expression.startswith(":"):
            try:
                limit = int(expression[1:])
            except ValueError as exc:
                raise ValueError(f"Column range must be :N, got {expression!r}") from exc
            if not 0 <= limit <= len(fieldnames):
                raise ValueError(f"Column range must be between 0 and {len(fieldnames)}")
            return list(fieldnames[:limit])
        return split_fields(expression)

    @staticmethod
    def output_fields(selected: list[str], rename_map: dict[str, str], rename_to: str) -> list[str]:
        positional = split_fields(rename_to)
        if positional:
            if len(positional) != len(selected):
                raise ValueError(f"rename_to length ({len(positional)}) must match selected columns ({len(selected)})")
            return positional
        return [rename_map.get(name, name) for name in selected]

"""Stable Python sorting for rectangular delimited files."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .adapter import (
    OUTPUT_TYPES,
    PythonDataTransformNode,
    as_number,
    node_output_dir,
    output_delimiter_and_extension,
    path_value,
    split_fields,
    validate_choice,
)


SORT_TYPES = ("auto", "string", "numeric")
SEPARATORS = ("auto", "comma", "tab", "space")


class SortFileNode(PythonDataTransformNode):
    """Stably sort a rectangular delimited file by names or zero-based indices."""

    NODE_ID = "sort_file"
    DISPLAY_NAME = "Sort File"
    DESCRIPTION = "Stably sort a rectangular delimited file by named columns or zero-based indices."
    SEARCH_ALIASES = ["sort", "order", "reorder", "ascending", "descending", "numeric sort"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("sorted_file",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/functions.html#sorted"
    UPSTREAM_SOURCE = "built-in sorted stability; Lib/csv.py"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed or ragged rows, absent columns, invalid indices, separators, sort types, "
        "and non-numeric cells in numeric mode are fatal; equal keys preserve input order."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Delimited text file"}),
                "sort_column": (
                    "STRING",
                    {"default": "", "description": "Column name or zero-based index; comma-separated"},
                ),
            },
            "optional": {
                "sort_type": (list(SORT_TYPES), {"default": "auto"}),
                "ascending": ("BOOLEAN", {"default": True}),
                "has_header": ("BOOLEAN", {"default": True}),
                "separator": (list(SEPARATORS), {"default": "auto"}),
                "output_type": (list(OUTPUT_TYPES), {"default": "AUTO"}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not path_value(inputs.get("file")):
            return "Input 'file' must be a non-empty path-like value"
        validation = validate_choice(inputs.get("sort_type", "auto"), "sort_type", SORT_TYPES)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("separator", "auto"), "separator", SEPARATORS)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("output_type", "AUTO"), "output_type", OUTPUT_TYPES)

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        input_path = Path(path_value(kwargs["file"])).expanduser()
        separator = self.separator(str(kwargs.get("separator", "auto")), input_path)
        rows = self.read_rows(input_path, separator)
        has_header = bool(kwargs.get("has_header", True))
        header = rows[0] if has_header else None
        data_rows = rows[1:] if has_header else rows
        width = len(header) if header is not None else len(data_rows[0])
        indexes = self.sort_indexes(str(kwargs.get("sort_column", "")), header, width)
        sort_type = str(kwargs.get("sort_type", "auto"))
        sorted_rows = sorted(
            data_rows,
            key=lambda row: self.sort_key(row, indexes, sort_type),
            reverse=not bool(kwargs.get("ascending", True)),
        )
        output_separator, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), input_path)
        output_path = node_output_dir(self, context) / f"{input_path.stem}.sorted{extension}"
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=output_separator, lineterminator="\n")
            if header is not None:
                writer.writerow(header)
            writer.writerows(sorted_rows)
        return (str(output_path),)

    @staticmethod
    def separator(mode: str, path: Path) -> str:
        normalized = mode.lower()
        if normalized == "comma":
            return ","
        if normalized == "tab":
            return "\t"
        if normalized == "space":
            return " "
        return "," if path.suffix.lower() == ".csv" else "\t"

    @staticmethod
    def read_rows(path: Path, separator: str) -> list[list[str]]:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [row for row in csv.reader(handle, delimiter=separator) if row]
        if not rows:
            raise ValueError(f"Delimited file is empty: {path}")
        width = len(rows[0])
        if width == 0:
            raise ValueError(f"Delimited file has no columns: {path}")
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != width:
                raise ValueError(f"Delimited row {line_number} has {len(row)} fields; expected {width}")
        return rows

    @staticmethod
    def sort_indexes(expression: str, header: list[str] | None, width: int) -> list[int]:
        if not expression.strip():
            return list(range(width))
        indexes: list[int] = []
        for item in split_fields(expression):
            if header is not None and not item.isdecimal():
                if item not in header:
                    raise ValueError(f"Sort column {item!r} not found")
                index = header.index(item)
            else:
                try:
                    index = int(item)
                except ValueError as exc:
                    raise ValueError(f"Sort column index must be an integer: {item}") from exc
            if not 0 <= index < width:
                raise ValueError(f"Sort column index out of range: {index}")
            indexes.append(index)
        if len(indexes) != len(set(indexes)):
            raise ValueError("Sort columns must be unique")
        return indexes

    @classmethod
    def sort_key(cls, row: list[str], indexes: list[int], sort_type: str) -> tuple[Any, ...]:
        return tuple(cls.sort_value(row[index], sort_type) for index in indexes)

    @staticmethod
    def sort_value(value: str, sort_type: str) -> Any:
        if sort_type == "string":
            return value
        if sort_type == "numeric":
            return as_number(value)
        try:
            return 0, as_number(value)
        except ValueError:
            return 1, value

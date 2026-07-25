"""Strict matrix-like CSV/TSV transposition."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
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
    validate_choice,
    write_table,
)


class TransposeTableNode(PythonDataTransformNode):
    """Use one ID column as the transposed output header axis."""

    NODE_ID = "transpose_table"
    DISPLAY_NAME = "Transpose Table"
    DESCRIPTION = "Transpose a CSV/TSV matrix using one unique, non-empty ID column as the new header axis."
    SEARCH_ALIASES = [
        "transpose",
        "pivot",
        "flip",
        "swap axes",
        "expression matrix transpose",
        "genes as rows",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("transposed_table",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; ordered dict insertion semantics"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, absent ID columns, empty or duplicate IDs, and header collisions are "
        "fatal; output row and column order follow the input."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"table": ("FILE", {"description": "CSV or TSV table with a header row"})},
            "optional": {
                "id_column": ("STRING", {"default": "", "description": "Defaults to the first column"}),
                "new_header": ("STRING", {"default": ""}),
                "output_type": (list(OUTPUT_TYPES), {"default": "AUTO"}),
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
        id_column = str(kwargs.get("id_column", "") or fieldnames[0]).strip()
        if id_column not in fieldnames:
            raise ValueError(f"ID column {id_column!r} not found")
        output_ids = [row.get(id_column, "") for row in rows]
        if any(not value for value in output_ids):
            raise ValueError("ID column contains an empty value")
        duplicate_ids = sorted(value for value, count in Counter(output_ids).items() if count > 1)
        if duplicate_ids:
            raise ValueError(f"ID column contains duplicate values: {', '.join(duplicate_ids)}")
        index_header = str(kwargs.get("new_header", "") or id_column).strip()
        if not index_header:
            raise ValueError("Transposed index header must be non-empty")
        if index_header in output_ids:
            raise ValueError(f"Transposed index header collides with ID value: {index_header}")
        value_columns = [name for name in fieldnames if name != id_column]
        output_fields = [index_header, *output_ids]
        output_rows = [
            {index_header: column, **{row[id_column]: row.get(column, "") for row in rows}} for column in value_columns
        ]
        output_delimiter, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), table)
        output_path = node_output_dir(self, context) / f"{table.stem}.transposed{extension}"
        write_table(output_path, output_fields, output_rows, output_delimiter)
        return (str(output_path),)

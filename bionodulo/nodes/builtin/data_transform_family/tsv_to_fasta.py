"""Strict delimited-table to FASTA conversion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    DELIMITER_MODES,
    PythonDataTransformNode,
    delimiter_for,
    fasta_header,
    fasta_sequence,
    node_output_dir,
    path_value,
    read_table,
    validate_choice,
    validate_int,
    wrap_sequence,
)


class TSVToFastaNode(PythonDataTransformNode):
    """Convert one sequence-bearing CSV/TSV row into one FASTA record."""

    NODE_ID = "tsv_to_fasta"
    DISPLAY_NAME = "TSV to FASTA"
    DESCRIPTION = "Convert a CSV/TSV table with explicit ID and sequence columns to FASTA."
    SEARCH_ALIASES = ["tsv", "csv", "fasta", "sequence", "convert", "table"]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("fasta",)
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; BioNodulo FASTA serialization contract"
    PRODUCT_ORIGIN_COMMIT = "ee282be0220566395a902805a180ffd0e5860a0b"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables, absent columns, empty IDs or sequences, colliding normalized IDs, "
        "and invalid line widths are fatal; no partial FASTA is returned."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with a header row"}),
                "id_column": ("STRING", {"description": "Column used for FASTA record IDs"}),
                "seq_column": ("STRING", {"description": "Column containing sequences"}),
            },
            "optional": {
                "delimiter": (list(DELIMITER_MODES), {"default": "auto"}),
                "line_width": (
                    "INT",
                    {"default": 80, "min": 0, "description": "Line width; zero disables wrapping"},
                ),
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
        for key in ("id_column", "seq_column"):
            if not str(inputs.get(key, "")).strip():
                return f"Input '{key}' must be non-empty"
        validation = validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)
        if validation is not True:
            return validation
        return validate_int(inputs.get("line_width", 80), "line_width", minimum=0)

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
        if not rows:
            raise ValueError("Input table contains no sequence rows")
        id_column = str(kwargs["id_column"]).strip()
        sequence_column = str(kwargs["seq_column"]).strip()
        missing = [name for name in (id_column, sequence_column) if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")
        line_width = int(kwargs.get("line_width", 80))

        normalized_ids: set[str] = set()
        lines: list[str] = []
        for row_number, row in enumerate(rows, start=2):
            record_id = fasta_header(row.get(id_column, ""))
            if record_id in normalized_ids:
                raise ValueError(f"Normalized FASTA ID is duplicated at table row {row_number}: {record_id}")
            normalized_ids.add(record_id)
            sequence = fasta_sequence(row.get(sequence_column, ""))
            if not sequence:
                raise ValueError(f"Table row {row_number} has an empty sequence")
            lines.append(f">{record_id}")
            lines.extend(wrap_sequence(sequence, line_width))

        output_path = node_output_dir(self, context) / f"{table.stem}.fasta"
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return (str(output_path),)

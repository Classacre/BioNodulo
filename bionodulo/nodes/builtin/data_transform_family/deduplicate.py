"""Stable table-row and FASTA-sequence deduplication."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, TypeVar

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
    wrap_sequence,
    write_table,
)


KEEP_MODES = ("first", "last", "none")
RecordT = TypeVar("RecordT")


class DeduplicateNode(PythonDataTransformNode):
    """Deduplicate rows by selected fields or FASTA records by sequence."""

    NODE_ID = "deduplicate"
    DISPLAY_NAME = "Deduplicate"
    DESCRIPTION = "Deduplicate CSV/TSV rows by selected columns or FASTA records by uppercase sequence."
    SEARCH_ALIASES = [
        "deduplicate",
        "remove duplicates",
        "unique",
        "distinct",
        "drop duplicates",
        "fasta dedup",
    ]
    RETURN_TYPES = ("FILE", "FILE")
    RETURN_NAMES = ("deduplicated", "duplicates")
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/collections.html#collections.Counter"
    UPSTREAM_SOURCE = "Lib/csv.py; collections.Counter; stable list ordering"
    PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
    EXIT_SEMANTICS = (
        "Missing files, malformed tables or FASTA, absent subset columns, unsupported keep modes, and invalid "
        "formats are fatal; both retained and duplicate artifacts are always written."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"table": ("FILE", {"description": "CSV, TSV, or FASTA input"})},
            "optional": {
                "subset_columns": ("STRING", {"default": "", "description": "Table key columns"}),
                "keep": (list(KEEP_MODES), {"default": "first"}),
                "sort_before": ("BOOLEAN", {"default": False}),
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
        validation = validate_choice(inputs.get("keep", "first"), "keep", KEEP_MODES)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("delimiter", "auto"), "delimiter", DELIMITER_MODES)
        if validation is not True:
            return validation
        return validate_choice(inputs.get("output_type", "AUTO"), "output_type", OUTPUT_TYPES)

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        input_path = Path(path_value(kwargs["table"])).expanduser()
        keep = str(kwargs.get("keep", "first"))
        if self.is_fasta(input_path):
            return self.deduplicate_fasta(input_path, keep, context)

        fieldnames, rows = read_table(
            input_path,
            delimiter_for(kwargs.get("delimiter", "auto"), input_path),
        )
        key_columns = split_fields(kwargs.get("subset_columns", "")) or list(fieldnames)
        missing = [name for name in key_columns if name not in fieldnames]
        if missing:
            raise ValueError(f"Column(s) not found: {', '.join(missing)}")
        if len(key_columns) != len(set(key_columns)):
            raise ValueError("subset_columns must be unique")
        working_rows = list(rows)
        if bool(kwargs.get("sort_before", False)):
            working_rows.sort(key=lambda row: tuple(row[name] for name in fieldnames))
        retained, duplicates = self.partition_records(
            working_rows,
            keep,
            key=lambda row: tuple(row.get(name, "") for name in key_columns),
        )
        output_delimiter, extension = output_delimiter_and_extension(kwargs.get("output_type", "AUTO"), input_path)
        output_dir = node_output_dir(self, context)
        retained_path = output_dir / f"{input_path.stem}.deduplicated{extension}"
        duplicates_path = output_dir / f"{input_path.stem}.duplicates{extension}"
        write_table(retained_path, fieldnames, retained, output_delimiter)
        write_table(duplicates_path, fieldnames, duplicates, output_delimiter)
        return str(retained_path), str(duplicates_path)

    @staticmethod
    def partition_records(
        records: list[RecordT],
        keep: str,
        *,
        key: Any,
    ) -> tuple[list[RecordT], list[RecordT]]:
        keys = [key(record) for record in records]
        if keep == "none":
            counts = Counter(keys)
            return (
                [record for record, record_key in zip(records, keys, strict=True) if counts[record_key] == 1],
                [record for record, record_key in zip(records, keys, strict=True) if counts[record_key] > 1],
            )
        retained_indexes: set[int] = set()
        duplicate_indexes: set[int] = set()
        seen: set[Any] = set()
        indexes = range(len(records)) if keep == "first" else range(len(records) - 1, -1, -1)
        for index in indexes:
            if keys[index] in seen:
                duplicate_indexes.add(index)
            else:
                seen.add(keys[index])
                retained_indexes.add(index)
        return (
            [record for index, record in enumerate(records) if index in retained_indexes],
            [record for index, record in enumerate(records) if index in duplicate_indexes],
        )

    @staticmethod
    def is_fasta(path: Path) -> bool:
        return path.suffix.lower() in {".fa", ".fna", ".faa", ".fasta"}

    @classmethod
    def deduplicate_fasta(cls, input_path: Path, keep: str, context: Any) -> tuple[str, str]:
        records = cls.read_fasta(input_path)
        retained, duplicates = cls.partition_records(records, keep, key=lambda record: record[1])
        output_dir = node_output_dir(cls(), context)
        retained_path = output_dir / f"{input_path.stem}.deduplicated.fasta"
        duplicates_path = output_dir / f"{input_path.stem}.duplicates.fasta"
        cls.write_fasta(retained_path, retained)
        cls.write_fasta(duplicates_path, duplicates)
        return str(retained_path), str(duplicates_path)

    @staticmethod
    def read_fasta(path: Path) -> list[tuple[str, str]]:
        records: list[tuple[str, str]] = []
        header = ""
        sequence_parts: list[str] = []
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header:
                    sequence = "".join(sequence_parts).upper()
                    if not sequence:
                        raise ValueError(f"FASTA record {header} has an empty sequence")
                    records.append((header, sequence))
                header = line
                sequence_parts = []
            elif not header:
                raise ValueError(f"FASTA sequence appears before a header at line {line_number}")
            else:
                sequence_parts.append(line)
        if header:
            sequence = "".join(sequence_parts).upper()
            if not sequence:
                raise ValueError(f"FASTA record {header} has an empty sequence")
            records.append((header, sequence))
        if not records:
            raise ValueError(f"FASTA file has no records: {path}")
        return records

    @staticmethod
    def write_fasta(path: Path, records: list[tuple[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for header, sequence in records:
                handle.write(f"{header}\n")
                for line in wrap_sequence(sequence, 60):
                    handle.write(f"{line}\n")

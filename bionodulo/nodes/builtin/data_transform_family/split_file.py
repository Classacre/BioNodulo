"""File splitting utility node."""
from __future__ import annotations

import csv
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

from .adapter import PythonDataTransformNode


class SplitFileNode(PythonDataTransformNode):
    """Split a file into multiple chunks."""

    NODE_ID = "split_file"
    DISPLAY_NAME = "Split File"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Split a file into chunks by line count, column value, approximate file size, "
        "or record count."
    )
    SEARCH_ALIASES = [
        "split",
        "chunk",
        "partition",
        "divide",
        "shard",
        "split csv",
        "split fastq",
        "split by chromosome",
        "batch split",
        "file chunks",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("chunks_dir",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    PRODUCT_SOURCE_COMMIT = "45518cfd3754b40ae44304bd65bc17d5ee6e2816"
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/data_transform_family/split_file.py"
    PRODUCT_SOURCE_SYMBOL = "SplitFileNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://docs.python.org/3.12/library/pathlib.html",
    )
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_csv_runtime": RUNTIME_DOCUMENTATION_URLS[0],
        "python_pathlib_runtime": RUNTIME_DOCUMENTATION_URLS[1],
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; unsupported split modes, invalid chunk "
        "sizes, malformed records or tables, missing columns, and file I/O errors raise."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"description": "Input file to split"}),
                "split_mode": (
                    "STRING",
                    {
                        "default": "by_line_count",
                        "options": ["by_line_count", "by_column_value", "by_file_size", "by_record_count"],
                    },
                ),
            },
            "optional": {
                "lines_per_chunk": ("INT", {"default": 1000, "min": 1, "max": 10000000}),
                "split_column": ("STRING", {"default": ""}),
                "max_size_mb": ("FLOAT", {"default": 100.0, "min": 1.0, "max": 10000.0}),
                "records_per_chunk": ("INT", {"default": 1000, "min": 1, "max": 10000000}),
                "has_header": ("BOOLEAN", {"default": True}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV", "FASTQ", "FASTA"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["file"]))
        split_mode = str(kwargs.get("split_mode", "by_line_count") or "by_line_count")
        output_dir = self._chunks_dir(input_path, context)
        output_dir.mkdir(parents=True, exist_ok=True)
        separator, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)

        if split_mode == "by_line_count":
            self._split_by_line_count(
                input_path,
                output_dir,
                separator,
                extension,
                int(kwargs.get("lines_per_chunk", 1000) or 1000),
                bool(kwargs.get("has_header", True)),
            )
        elif split_mode == "by_column_value":
            self._split_by_column_value(
                input_path,
                output_dir,
                separator,
                extension,
                str(kwargs.get("split_column", "") or ""),
                bool(kwargs.get("has_header", True)),
            )
        elif split_mode == "by_file_size":
            self._split_by_file_size(
                input_path,
                output_dir,
                extension,
                float(kwargs.get("max_size_mb", 100.0) or 100.0),
            )
        elif split_mode == "by_record_count":
            self._split_by_record_count(
                input_path,
                output_dir,
                separator,
                extension,
                int(kwargs.get("records_per_chunk", 1000) or 1000),
                bool(kwargs.get("has_header", True)),
            )
        else:
            raise ValueError(f"Unsupported split_mode: {split_mode}")

        return (str(output_dir),)

    @classmethod
    def _chunks_dir(cls, input_path: Path, context: Any) -> Path:
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        return base / cls.NODE_ID / f"{input_path.stem}_chunks"

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "FASTQ":
            return "\n", ".fastq"
        if normalized == "FASTA":
            return "\n", ".fasta"
        if normalized != "AUTO":
            raise ValueError(f"Unsupported output_type: {output_type}")
        suffix = input_path.suffix.lower()
        if suffix == ".csv":
            return ",", ".csv"
        if suffix in {".fq", ".fastq"}:
            return "\n", suffix
        if suffix in {".fa", ".fasta", ".fna"}:
            return "\n", suffix
        return "\t", ".tsv"

    @staticmethod
    def _input_separator(path: Path, output_separator: str) -> str:
        if path.suffix.lower() == ".csv":
            return ","
        if output_separator in {",", "\t"}:
            return output_separator
        return "\t"

    def _split_by_line_count(
        self,
        input_path: Path,
        output_dir: Path,
        output_separator: str,
        extension: str,
        lines_per_chunk: int,
        has_header: bool,
    ) -> None:
        if lines_per_chunk < 1:
            raise ValueError("lines_per_chunk must be at least 1")
        input_separator = self._input_separator(input_path, output_separator)
        with input_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh, delimiter=input_separator)
            header = next(reader, None) if has_header else None
            chunk: list[list[str]] = []
            index = 1
            for row in reader:
                chunk.append(row)
                if len(chunk) >= lines_per_chunk:
                    self._write_rows(output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}", header, chunk, output_separator)
                    chunk = []
                    index += 1
            if chunk or index == 1:
                self._write_rows(output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}", header, chunk, output_separator)

    def _split_by_column_value(
        self,
        input_path: Path,
        output_dir: Path,
        output_separator: str,
        extension: str,
        split_column: str,
        has_header: bool,
    ) -> None:
        if not has_header:
            raise ValueError("by_column_value requires has_header=True")
        if not split_column.strip():
            raise ValueError("split_column is required for by_column_value")

        input_separator = self._input_separator(input_path, output_separator)
        with input_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=input_separator)
            if reader.fieldnames is None:
                raise ValueError(f"Table has no header row: {input_path}")
            if split_column not in reader.fieldnames:
                raise ValueError(f"Split column {split_column!r} not found")

            groups: OrderedDict[str, list[dict[str, str]]] = OrderedDict()
            for row in reader:
                groups.setdefault(row.get(split_column, ""), []).append(dict(row))

        for value, rows in groups.items():
            safe_value = self._safe_name(value) or "blank"
            out_path = output_dir / f"{input_path.stem}.{safe_value}{extension}"
            with out_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=reader.fieldnames, delimiter=output_separator)
                writer.writeheader()
                writer.writerows(rows)

    @staticmethod
    def _split_by_file_size(input_path: Path, output_dir: Path, extension: str, max_size_mb: float) -> None:
        max_bytes = max(1, int(max_size_mb * 1024 * 1024))
        index = 1
        current_size = 0
        out_fh = None
        try:
            with input_path.open("rb") as source:
                for line in source:
                    if out_fh is None or (current_size > 0 and current_size + len(line) > max_bytes):
                        if out_fh is not None:
                            out_fh.close()
                        out_fh = (output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}").open("wb")
                        index += 1
                        current_size = 0
                    out_fh.write(line)
                    current_size += len(line)
        finally:
            if out_fh is not None:
                out_fh.close()

    @staticmethod
    def _split_by_record_count(
        input_path: Path,
        output_dir: Path,
        output_separator: str,
        extension: str,
        records_per_chunk: int,
        has_header: bool,
    ) -> None:
        if records_per_chunk < 1:
            raise ValueError("records_per_chunk must be at least 1")
        suffix = input_path.suffix.lower()
        if output_separator in {",", "\t"} and suffix not in {".fa", ".fasta", ".fna", ".fq", ".fastq"}:
            SplitFileNode()._split_by_line_count(
                input_path,
                output_dir,
                output_separator,
                extension,
                records_per_chunk,
                has_header,
            )
            return

        lines_per_record = 4 if suffix in {".fq", ".fastq"} else None
        if lines_per_record is None:
            SplitFileNode._split_fasta_records(input_path, output_dir, extension, records_per_chunk)
            return

        with input_path.open("r", encoding="utf-8") as source:
            index = 1
            records: list[str] = []
            while True:
                record = [source.readline() for _ in range(lines_per_record)]
                if not record[0]:
                    break
                if any(line == "" for line in record):
                    raise ValueError(f"Incomplete FASTQ record in {input_path}")
                records.extend(record)
                if len(records) // lines_per_record >= records_per_chunk:
                    (output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}").write_text("".join(records), encoding="utf-8")
                    index += 1
                    records = []
            if records:
                (output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}").write_text("".join(records), encoding="utf-8")

    @staticmethod
    def _split_fasta_records(input_path: Path, output_dir: Path, extension: str, records_per_chunk: int) -> None:
        index = 1
        records: list[str] = []
        current: list[str] = []
        with input_path.open("r", encoding="utf-8") as source:
            for line in source:
                if line.startswith(">") and current:
                    records.append("".join(current))
                    current = []
                    if len(records) >= records_per_chunk:
                        (output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}").write_text("".join(records), encoding="utf-8")
                        index += 1
                        records = []
                current.append(line)
            if current:
                records.append("".join(current))
            if records:
                (output_dir / f"{input_path.stem}.chunk_{index:03d}{extension}").write_text("".join(records), encoding="utf-8")

    @staticmethod
    def _write_rows(path: Path, header: list[str] | None, rows: list[list[str]], separator: str) -> None:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh, delimiter=separator, lineterminator="\n")
            if header is not None:
                writer.writerow(header)
            writer.writerows(rows)

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip()).strip("._")

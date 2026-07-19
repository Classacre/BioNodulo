"""Sample-subsetting node for sequence and table files."""
from __future__ import annotations

import random
import csv
import math
from pathlib import Path
from typing import Any, Iterable

from bionodulo.nodes.base import BaseNode

from .adapter import PythonDataTransformNode


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _output_path(node: BaseNode, context: Any, input_path: Path, output_type: str = "AUTO") -> Path:
    extension = _output_extension(input_path, output_type)
    return _node_output_dir(node, context) / f"{input_path.stem}.subset{extension}"


def _output_extension(input_path: Path, output_type: str) -> str:
    normalized = str(output_type or "AUTO").upper()
    if normalized == "CSV":
        return ".csv"
    if normalized == "TSV":
        return ".tsv"
    if normalized == "FASTQ":
        return ".fastq"
    if normalized == "FASTA":
        return ".fasta"
    if normalized != "AUTO":
        raise ValueError(f"Unsupported output_type: {output_type}")
    return input_path.suffix


def _looks_like_fastq(path: Path) -> bool:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    return any(suffix in suffixes for suffix in {".fastq", ".fq"})


def _looks_like_fasta(path: Path) -> bool:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    return any(suffix in suffixes for suffix in {".fasta", ".fa", ".fna", ".faa", ".fas"})


def _looks_like_table(path: Path) -> bool:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    return any(suffix in suffixes for suffix in {".csv", ".tsv"})


def _take_first(records: list[list[str]], n: int) -> list[list[str]]:
    return records[:n]


def _take_every_nth(records: list[list[str]], every_n: int) -> list[list[str]]:
    if every_n < 1:
        raise ValueError("every_n must be at least 1")
    return [record for index, record in enumerate(records, start=1) if index % every_n == 0]


def _take_random(records: list[list[str]], n: int, seed: int) -> list[list[str]]:
    if n >= len(records):
        return list(records)
    rng = random.Random(seed)
    indexes = sorted(rng.sample(range(len(records)), n))
    return [records[index] for index in indexes]


def _write_records(path: Path, records: Iterable[list[str]]) -> None:
    path.write_text("".join(line for record in records for line in record), encoding="utf-8")


def _read_fasta_records(path: Path) -> list[list[str]]:
    records: list[list[str]] = []
    current: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(">"):
                if current:
                    records.append(current)
                current = [line]
            elif current:
                current.append(line)
            elif line.strip():
                raise ValueError(f"FASTA sequence data appears before a header in {path}")
        if current:
            records.append(current)
    return records


def _read_fastq_records(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8") as fh:
        lines = fh.readlines()
    if len(lines) % 4 != 0:
        raise ValueError(f"FASTQ file must contain a multiple of 4 lines: {path}")
    records = [lines[index:index + 4] for index in range(0, len(lines), 4)]
    for record in records:
        if record and not record[0].startswith("@"):
            raise ValueError(f"FASTQ record header must start with @ in {path}")
    return records


class SampleSubsetNode(PythonDataTransformNode):
    """Subset records from sequence and table files."""

    NODE_ID = "sample_subset"
    DISPLAY_NAME = "Sample Subset"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Randomly subset records from sequence or table files. Supports reproducible "
        "random sampling, first-N selection, and every-Nth selection."
    )
    SEARCH_ALIASES = [
        "sample",
        "subset",
        "downsample",
        "random sample",
        "fastq subset",
        "fasta subset",
        "reduce size",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("subset_file",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    PRODUCT_SOURCE_COMMIT = "45518cfd3754b40ae44304bd65bc17d5ee6e2816"
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/data_transform_family/sample_subset.py"
    PRODUCT_SOURCE_SYMBOL = "SampleSubsetNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/random.html"
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://docs.python.org/3.12/library/csv.html",
    )
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_random_runtime": RUNTIME_DOCUMENTATION_URLS[0],
        "python_csv_runtime": RUNTIME_DOCUMENTATION_URLS[1],
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; malformed FASTA/FASTQ/table records, "
        "unsupported modes or formats, invalid sampling values, and file I/O errors raise."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FASTQ,FASTA,CSV,TSV,FASTQ_LIST", {}),
                "n": ("INT", {"default": 1000, "min": 1, "max": 100000000}),
            },
            "optional": {
                "mode": (["random", "first_n", "every_nth", "stratified"], {"default": "random"}),
                "seed": ("INT", {"default": 42, "min": 0, "max": 999999}),
                "stratify_column": ("STRING", {"default": ""}),
                "every_n": ("INT", {"default": 10, "min": 2, "max": 1000000}),
                "output_type": (["AUTO", "CSV", "TSV", "FASTQ", "FASTA"], {"default": "AUTO"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["file"]))
        n = int(kwargs.get("n", 1000))
        if n < 1:
            raise ValueError("n must be at least 1")
        mode = str(kwargs.get("mode", "random") or "random")
        seed = int(kwargs.get("seed", 42))
        every_n = int(kwargs.get("every_n", 10))
        output_type = str(kwargs.get("output_type", "AUTO") or "AUTO")
        stratify_column = str(kwargs.get("stratify_column", "") or "")
        output_path = _output_path(self, context, input_path, output_type)

        if _looks_like_fastq(input_path):
            records = self._subset_records(_read_fastq_records(input_path), mode, n, seed, every_n)
            _write_records(output_path, records)
            return (str(output_path),)

        if _looks_like_fasta(input_path):
            records = self._subset_records(_read_fasta_records(input_path), mode, n, seed, every_n)
            _write_records(output_path, records)
            return (str(output_path),)

        if _looks_like_table(input_path):
            self._subset_table(input_path, output_path, mode, n, seed, every_n, stratify_column)
            return (str(output_path),)

        raise ValueError(f"Unsupported sample subset input file type: {input_path}")

    @staticmethod
    def _subset_records(
        records: list[list[str]],
        mode: str,
        n: int,
        seed: int,
        every_n: int,
    ) -> list[list[str]]:
        if mode == "first_n":
            return _take_first(records, n)
        if mode == "every_nth":
            return _take_every_nth(records, every_n)
        if mode == "random":
            return _take_random(records, n, seed)
        raise ValueError(f"Unsupported sampling mode: {mode}")

    @staticmethod
    def _subset_table(
        input_path: Path,
        output_path: Path,
        mode: str,
        n: int,
        seed: int,
        every_n: int,
        stratify_column: str,
    ) -> None:
        input_delimiter = "," if input_path.suffix.lower() == ".csv" else "\t"
        with input_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=input_delimiter)
            if reader.fieldnames is None:
                raise ValueError(f"Table has no header row: {input_path}")
            fieldnames = list(reader.fieldnames)
            rows = [dict(row) for row in reader]

        if mode == "first_n":
            selected = _take_first(rows, n)
        elif mode == "every_nth":
            selected = _take_every_nth(rows, every_n)
        elif mode == "random":
            selected = _take_random(rows, n, seed)
        elif mode == "stratified":
            selected = SampleSubsetNode._stratified_sample(rows, n, seed, stratify_column)
        else:
            raise ValueError(f"Unsupported sampling mode: {mode}")

        output_delimiter = "," if output_path.suffix.lower() == ".csv" else "\t"
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=output_delimiter)
            writer.writeheader()
            writer.writerows(selected)

    @staticmethod
    def _stratified_sample(rows: list[dict[str, str]], n: int, seed: int, stratify_column: str) -> list[dict[str, str]]:
        if not stratify_column:
            raise ValueError("stratify_column is required for stratified sampling")
        groups: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            if stratify_column not in row:
                raise ValueError(f"Stratify column {stratify_column!r} not found")
            groups.setdefault(row.get(stratify_column, ""), []).append(row)

        rng = random.Random(seed)
        total = len(rows)
        target = min(n, total)
        quotas: dict[str, int] = {}
        remainders: list[tuple[float, str]] = []
        for key, group_rows in groups.items():
            exact = target * (len(group_rows) / total) if total else 0
            quota = min(len(group_rows), math.floor(exact))
            quotas[key] = quota
            remainders.append((exact - quota, key))

        remaining = target - sum(quotas.values())
        for _remainder, key in sorted(remainders, reverse=True):
            if remaining <= 0:
                break
            if quotas[key] < len(groups[key]):
                quotas[key] += 1
                remaining -= 1

        selected: list[dict[str, str]] = []
        for key in groups:
            group_rows = groups[key]
            quota = quotas[key]
            if quota >= len(group_rows):
                selected.extend(group_rows)
            else:
                selected.extend(group_rows[index] for index in sorted(rng.sample(range(len(group_rows)), quota)))
        return selected

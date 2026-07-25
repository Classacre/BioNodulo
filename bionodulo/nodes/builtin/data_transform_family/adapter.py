"""Shared strict CSV/TSV/JSON helpers for product-native transform nodes."""

from __future__ import annotations

import csv
import json
import math
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.base import BaseNode


PYTHON_VERSION = "3.12.13"
CPYTHON_GIT_URL = "https://github.com/python/cpython.git"
CPYTHON_GIT_COMMIT = "3bb231a6a5dc02b95658877318bf61501a7209e9"
PRODUCT_BASE_COMMIT = "a32a426c03ce4c925bf7dcdbd2cf08fbdedd55e9"
PRODUCT_ORIGIN_COMMIT = "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d"
TABLE_FORMATS = ("csv", "tsv", "json")
DELIMITER_MODES = ("auto", "csv", "tsv")
OUTPUT_TYPES = ("AUTO", "CSV", "TSV")


class PythonDataTransformNode(BaseNode):
    """Metadata shared by deterministic Python 3.12 data transforms."""

    NODE_ID = ""
    CATEGORY = "data_transform"
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: ClassVar[list[str]] = []
    REQUIRED_CONDA_PACKAGES: ClassVar[list[str]] = []
    VERSION = "2.0.0"
    GIT_URL = CPYTHON_GIT_URL
    GIT_COMMIT = CPYTHON_GIT_COMMIT
    RUNTIME_VERSION = PYTHON_VERSION
    PRODUCT_SOURCE_COMMIT = PRODUCT_BASE_COMMIT
    ENVIRONMENT = {"python": PYTHON_VERSION, "stdlib_only": True}


class PythonPrimitiveNode(PythonDataTransformNode):
    """Python-backed scalar primitive rather than a file transform."""

    CATEGORY = "primitive"


def path_value(value: Any) -> str:
    try:
        path = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return path.strip()


def require_file(value: Any, key: str) -> Path:
    path = path_value(value)
    if not path:
        raise ValueError(f"Input '{key}' must be a non-empty path-like value")
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise ValueError(f"Input file does not exist: {resolved}")
    return resolved


def node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    output_dir = base / node.NODE_ID
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def validate_choice(value: Any, key: str, choices: Iterable[str], *, casefold: bool = False) -> bool | str:
    allowed = tuple(choices)
    candidate = str(value)
    if casefold:
        lookup = {item.casefold() for item in allowed}
        valid = candidate.casefold() in lookup
    else:
        valid = candidate in allowed
    if not valid:
        return f"Input '{key}' must be one of: {', '.join(allowed)}"
    return True


def validate_int(
    value: Any,
    key: str,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> bool | str:
    if isinstance(value, bool) or not isinstance(value, int):
        return f"Input '{key}' must be an integer"
    if minimum is not None and value < minimum:
        return f"Input '{key}' must be at least {minimum}"
    if maximum is not None and value > maximum:
        return f"Input '{key}' must be at most {maximum}"
    return True


def delimiter_for(mode: Any, path: str | Path) -> str:
    requested = str(mode or "auto").strip().lower()
    if requested == "csv":
        return ","
    if requested == "tsv":
        return "\t"
    if requested != "auto":
        raise ValueError(f"Unsupported delimiter: {mode}")
    return "," if Path(str(path)).suffix.lower() == ".csv" else "\t"


def output_delimiter_and_extension(output_type: Any, *input_paths: str | Path) -> tuple[str, str]:
    requested = str(output_type or "AUTO").strip().upper()
    if requested == "CSV":
        return ",", ".csv"
    if requested == "TSV":
        return "\t", ".tsv"
    if requested != "AUTO":
        raise ValueError(f"Unsupported output_type: {output_type}")
    all_csv = bool(input_paths) and all(Path(str(path)).suffix.lower() == ".csv" for path in input_paths)
    return (",", ".csv") if all_csv else ("\t", ".tsv")


def read_table(path: str | Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    input_path = Path(path)
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            fieldnames = next(reader)
        except StopIteration as exc:
            raise ValueError(f"Table is empty: {input_path}") from exc
        if not fieldnames or any(not name for name in fieldnames):
            raise ValueError(f"Table header contains an empty column name: {input_path}")
        duplicates = sorted({name for name in fieldnames if fieldnames.count(name) > 1})
        if duplicates:
            raise ValueError(f"Table header contains duplicate column(s): {', '.join(duplicates)}")

        rows: list[dict[str, str]] = []
        for line_number, values in enumerate(reader, start=2):
            if not values:
                continue
            if len(values) != len(fieldnames):
                raise ValueError(f"Table row {line_number} has {len(values)} fields; expected {len(fieldnames)}")
            rows.append(dict(zip(fieldnames, values, strict=True)))
    return fieldnames, rows


def write_table(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[Mapping[str, Any]],
    delimiter: str,
) -> None:
    if not fieldnames:
        raise ValueError("Output table must contain at least one column")
    if len(fieldnames) != len(set(fieldnames)):
        raise ValueError("Output table column names must be unique")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter=delimiter,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: format_scalar(row.get(name, "")) for name in fieldnames})


def split_fields(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def parse_rename_map(value: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for item in split_fields(value):
        if ":" not in item:
            raise ValueError(f"Rename entry must be old:new, got {item!r}")
        old, new = (part.strip() for part in item.split(":", 1))
        if not old or not new:
            raise ValueError(f"Rename entry must be old:new, got {item!r}")
        if old in mapping:
            raise ValueError(f"Rename source appears more than once: {old}")
        mapping[old] = new
    return mapping


def format_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def as_number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean values are not numeric table values")
    number = float(str(value).strip())
    if not math.isfinite(number):
        raise ValueError(f"Numeric value must be finite: {value!r}")
    return number


def normalize_table_format(value: Any, path: str | Path | None = None) -> str:
    requested = str(value or "auto").strip().lower()
    if requested == "auto":
        suffix = Path(str(path)).suffix.lower() if path else ""
        if suffix == ".json":
            return "json"
        if suffix == ".csv":
            return "csv"
        if suffix in {".tsv", ".tab"}:
            return "tsv"
        raise ValueError("input_format=auto requires a .csv, .tsv, .tab, or .json filename")
    if requested not in TABLE_FORMATS:
        raise ValueError(f"Unsupported table format: {value}")
    return requested


def fieldnames_from_records(records: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            name = str(key)
            if not name:
                raise ValueError("JSON record field names must be non-empty")
            if name not in seen:
                seen.add(name)
                fieldnames.append(name)
    return fieldnames


def read_records(path: str | Path, input_format: str) -> tuple[list[str], list[dict[str, Any]]]:
    if input_format in {"csv", "tsv"}:
        fieldnames, rows = read_table(path, "," if input_format == "csv" else "\t")
        return fieldnames, rows

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        payload = payload["rows"]
    elif isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("JSON input must be an object, a list of objects, or an object with a rows list")
    records = [dict(item) for item in payload]
    return fieldnames_from_records(records), records


def write_records(
    path: Path,
    output_format: str,
    fieldnames: list[str],
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(records, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
        return
    if not fieldnames:
        raise ValueError("Cannot write headerless CSV/TSV from records with no fields")
    write_table(path, fieldnames, records, "," if output_format == "csv" else "\t")


def safe_output_stem(value: Any, *, fallback: str) -> str:
    raw = Path(str(value or "")).stem
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._")
    return stem or fallback


def fasta_header(value: Any) -> str:
    header = re.sub(r"\s+", "_", str(value or "").strip())
    header = re.sub(r"[^A-Za-z0-9_.|:-]", "_", header)
    if not header:
        raise ValueError("FASTA record IDs must be non-empty")
    return header


def fasta_sequence(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).upper()


def wrap_sequence(sequence: str, line_width: int) -> list[str]:
    if line_width == 0:
        return [sequence]
    return [sequence[index : index + line_width] for index in range(0, len(sequence), line_width)]

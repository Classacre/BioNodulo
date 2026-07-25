"""Shared deterministic helpers for native reporting nodes."""

from __future__ import annotations

import csv
import os
from itertools import islice
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


PYTHON_VERSION = "3.12.13"
PYTHON_GIT_COMMIT = "3bb231a6a5dc02b95658877318bf61501a7209e9"
REPORTING_ORIGIN_COMMIT = "7523e9aaae5e1c6c3badb23b6b43a1d7798b9429"
REPORTING_BASELINE_BLOB = "8df764297b6cb3e452adc6ad556223074795d96b"
INTERNAL_GIT_URL = "https://github.com/Classacre/BioNodulo.git"


def path_value(value: Any) -> str:
    try:
        result = os.fsdecode(os.fspath(value))
    except TypeError:
        return ""
    return result if result.strip() else ""


def node_output_path(context: Any, node_id: str, filename: str) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context is not None else ".")
    output_dir = base / node_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def normalise_file_list(value: Any, *, label: str = "Report input") -> list[Path]:
    if value in (None, ""):
        return []
    if isinstance(value, set):
        items = sorted(value, key=str)
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [part.strip() for part in str(value).split(",") if part.strip()]
    paths: list[Path] = []
    for item in items:
        raw_path = path_value(item)
        if not raw_path:
            raise ValueError(f"{label} must contain non-empty path-like values")
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"{label} file not found: {path}")
        if not path.is_file():
            raise ValueError(f"{label} is not a regular file: {path}")
        paths.append(path)
    return paths


def section_names(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _sniff_delimiter(path: Path, handle: Any) -> str:
    sample = handle.read(8192)
    handle.seek(0)
    if not sample:
        return "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;|").delimiter
    except csv.Error:
        if path.suffix.lower() in {".tsv", ".tab"}:
            return "\t"
        counts = {candidate: sample.count(candidate) for candidate in (",", "\t", ";", "|")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def read_table_rows(path: Path, *, max_body_rows: int) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        delimiter = _sniff_delimiter(path, handle)
        reader = csv.reader(handle, delimiter=delimiter)
        header = next(reader, [])
        body = list(islice(reader, max_body_rows))
    return header, body


def theme_tokens(theme: str) -> dict[str, str]:
    if theme == "light":
        return {
            "bg": "#FFFFFF",
            "text": "#111827",
            "muted": "#475569",
            "section": "#F8FAFC",
            "border": "#CBD5E1",
            "accent": "#2563EB",
            "table_alt": "#F1F5F9",
        }
    if theme == "dark":
        return {
            "bg": "#0F172A",
            "text": "#E5E7EB",
            "muted": "#94A3B8",
            "section": "#1E293B",
            "border": "#334155",
            "accent": "#60A5FA",
            "table_alt": "#111827",
        }
    raise ValueError(f"Unsupported report theme: {theme}")


class ReportingNode(BaseNode):
    """Native reporting base pinned to its product and CPython authorities."""

    CATEGORY = "reporting"
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    GIT_URL = INTERNAL_GIT_URL
    GIT_COMMIT = REPORTING_ORIGIN_COMMIT
    SOURCE_AUTHORITIES = {
        "BioNodulo reporting baseline": (REPORTING_ORIGIN_COMMIT, REPORTING_BASELINE_BLOB),
        "CPython": (PYTHON_VERSION, PYTHON_GIT_COMMIT),
    }

"""Bounded RFC-style delimited-table preview contract."""

from __future__ import annotations

import csv
import html
from itertools import islice
from pathlib import Path
from typing import Any

from .adapter import (
    PythonUtilityNode,
    node_output_path,
    path_value,
    validate_int,
    validate_regular_file,
)


TABLE_EXTENSIONS = frozenset({".csv", ".tsv", ".txt", ".tab"})
DELIMITERS = ("auto", ",", "\t", ";", "|", " ")


def _delimiter(path: Path, handle: Any, choice: str) -> str:
    if choice != "auto":
        return "\t" if choice == "\\t" else choice
    sample = handle.read(8192)
    handle.seek(0)
    if not sample:
        return "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;| ").delimiter
    except csv.Error:
        if path.suffix.lower() in {".tsv", ".tab"}:
            return "\t"
        counts = {candidate: sample.count(candidate) for candidate in (",", "\t", ";", "|", " ")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


class TablePreviewNode(PythonUtilityNode):
    """Render a bounded CSV/TSV prefix without materialising the full table."""

    NODE_ID = "table_preview"
    DISPLAY_NAME = "Table Preview"
    DESCRIPTION = "Preview the head of a CSV/TSV table inline on the canvas"
    SEARCH_ALIASES = ["table", "csv", "tsv", "head", "preview", "data"]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; Modules/_csv.c; Lib/html/__init__.py"
    _TABLE_EXTS = set(TABLE_EXTENSIONS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": ("FILE", {"label": "Table file", "description": "CSV / TSV / TXT"}),
            },
            "optional": {
                "rows": ("INT", {"default": 25, "min": 1, "max": 500, "label": "Head rows"}),
                "delimiter": (
                    "STRING",
                    {
                        "default": "auto",
                        "options": list(DELIMITERS),
                        "label": "Delimiter",
                        "advanced": True,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = validate_regular_file(
            inputs.get("file"), extensions=TABLE_EXTENSIONS, label="Table file"
        )
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("rows", 25), "rows", minimum=1, maximum=500)
        if validation is not True:
            return validation
        delimiter = str(inputs.get("delimiter", "auto") or "auto")
        if delimiter == "\\t":
            delimiter = "\t"
        if delimiter not in DELIMITERS:
            return "Input 'delimiter' must be one of: auto, comma, tab, semicolon, pipe, or space"
        return True

    @staticmethod
    def _sniff_delimiter(line: str) -> str:
        try:
            return csv.Sniffer().sniff(line, delimiters="\t,;| ").delimiter
        except csv.Error:
            return ","

    async def run(self, **kwargs: Any) -> tuple[()]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        source = Path(path_value(kwargs["file"]))
        rows_limit = int(kwargs.get("rows", 25))
        delimiter_choice = str(kwargs.get("delimiter", "auto") or "auto")
        with source.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            delimiter = _delimiter(source, handle, delimiter_choice)
            reader = csv.reader(handle, delimiter=delimiter)
            header = next(reader, [])
            selected = list(islice(reader, rows_limit + 1))
        has_more = len(selected) > rows_limit
        body = selected[:rows_limit]

        thead = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
        body_html = "".join(
            "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
            for row in body
        )
        status = f"showing {len(body):,} data row(s)"
        if has_more:
            status += "; additional rows not shown"
        output_path = node_output_path(context, self.NODE_ID, "table.html")
        output_path.write_text(
            "<!doctype html><meta charset=utf-8>"
            f"<title>{html.escape(source.name)}</title>"
            "<style>body{font-family:system-ui,sans-serif;padding:12px;color:#0f172a}"
            "h1{font-size:13px;margin:0 0 8px;color:#475569}"
            "table{border-collapse:collapse;font-size:12px;width:100%}"
            "th,td{border:1px solid #e2e8f0;padding:4px 8px;text-align:left;vertical-align:top}"
            "th{background:#f1f5f9;position:sticky;top:0}"
            "tr:nth-child(even) td{background:#f8fafc}</style>"
            f"<h1>{html.escape(source.name)} - {html.escape(status)}</h1>"
            f"<table><thead><tr>{thead}</tr></thead><tbody>{body_html}</tbody></table>",
            encoding="utf-8",
        )
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Table Preview")
        return ()

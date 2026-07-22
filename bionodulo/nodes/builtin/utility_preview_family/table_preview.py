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


TABLE_EXTENSIONS = frozenset(
    {
        ".bed",
        ".bedgraph",
        ".csv",
        ".gff",
        ".kreport",
        ".narrowpeak",
        ".sf",
        ".tab",
        ".tsv",
        ".txt",
    }
)
DELIMITERS = ("auto", ",", "\t", ";", "|", " ")

_FIXED_HEADERS = {
    ".gff": ("seqid", "source", "type", "start", "end", "score", "strand", "phase", "attributes"),
    ".kreport": ("percentage", "clade_reads", "taxon_reads", "rank_code", "ncbi_taxid", "name"),
    ".narrowpeak": (
        "chrom",
        "start",
        "end",
        "name",
        "score",
        "strand",
        "signal_value",
        "p_value",
        "q_value",
        "peak",
    ),
}
_HEADERLESS_EXTENSIONS = frozenset({".bedgraph", *_FIXED_HEADERS})
_TAB_EXTENSIONS = frozenset({".bedgraph", ".gff", ".kreport", ".narrowpeak", ".sf"})


def _delimiter(path: Path, handle: Any, choice: str) -> str:
    if choice != "auto":
        return "\t" if choice == "\\t" else choice
    if path.suffix.lower() in _TAB_EXTENSIONS:
        return "\t"
    sample = handle.read(8192)
    handle.seek(0)
    if not sample:
        return "\t" if path.suffix.lower() in {".bed", ".tsv", ".tab"} else ","
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;| ").delimiter
    except csv.Error:
        if path.suffix.lower() in {".bed", ".tsv", ".tab"}:
            return "\t"
        counts = {candidate: sample.count(candidate) for candidate in (",", "\t", ";", "|", " ")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def _is_metadata_row(row: list[str], suffix: str) -> bool:
    if not row:
        return True
    marker = row[0].lstrip()
    if suffix == ".gff":
        return marker.startswith("#")
    if suffix in {".bedgraph", ".narrowpeak"}:
        lowered = marker.casefold()
        return lowered.startswith(("#", "browser ", "track "))
    return False


def _format_header(suffix: str, width: int) -> list[str]:
    fixed = _FIXED_HEADERS.get(suffix)
    if fixed is not None:
        return list(fixed)
    base = ["chrom", "start", "end", "value"]
    if width <= len(base):
        return base[:width]
    return [*base, *(f"column_{index}" for index in range(len(base) + 1, width + 1))]


def _header_and_rows(reader: Any, suffix: str, rows_limit: int) -> tuple[list[str], list[list[str]]]:
    if suffix not in _HEADERLESS_EXTENSIONS:
        return next(reader, []), list(islice(reader, rows_limit + 1))

    selected: list[list[str]] = []
    for row in reader:
        if suffix == ".gff" and row and row[0].lstrip().casefold().startswith("##fasta"):
            break
        if _is_metadata_row(row, suffix):
            continue
        selected.append(row)
        if len(selected) > rows_limit:
            break
    width = max((len(row) for row in selected), default=0)
    return _format_header(suffix, width), selected


class TablePreviewNode(PythonUtilityNode):
    """Render a bounded, format-aware tabular prefix without reading the full file."""

    NODE_ID = "table_preview"
    DISPLAY_NAME = "Table Preview"
    DESCRIPTION = (
        "Preview BED, bedGraph, GFF, narrowPeak, Kraken report, Salmon quant, "
        "CSV, or TSV data inline on the canvas"
    )
    SEARCH_ALIASES = [
        "table",
        "bed",
        "bedGraph",
        "gff",
        "narrowPeak",
        "kreport",
        "quant.sf",
        "csv",
        "tsv",
        "head",
        "preview",
        "data",
    ]
    RETURN_TYPES = ()
    RETURN_NAMES = ()
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/csv.html"
    UPSTREAM_SOURCE = "Lib/csv.py; Modules/_csv.c; Lib/html/__init__.py"
    FORMAT_SOURCE_AUTHORITIES = {
        "MACS2 narrowPeak": (
            "2.2.9.1",
            "1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c",
            "https://github.com/macs3-project/MACS/blob/"
            "1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c/README.md",
        ),
        "Prokka GFF3": (
            "1.15.6",
            "d7b72388989e1fba42c8c68482a36a70dbd3bac4",
            "https://github.com/tseemann/prokka/blob/"
            "d7b72388989e1fba42c8c68482a36a70dbd3bac4/bin/prokka",
        ),
        "MethylDackel bedGraph": (
            "0.6.1",
            "b6db120e96ec8cf9ab44e1b1074d2aa7af876932",
            "https://github.com/dpryan79/MethylDackel/blob/"
            "b6db120e96ec8cf9ab44e1b1074d2aa7af876932/README.md",
        ),
        "Salmon quant.sf": (
            "2.3.4",
            "d53fed6f0af6966a40825558f0edf71b6df7cf52",
            "https://github.com/COMBINE-lab/salmon/blob/"
            "d53fed6f0af6966a40825558f0edf71b6df7cf52/crates/salmon-quant/src/output.rs",
        ),
        "Bracken kreport": (
            "3.1",
            "cfeac04b6445c44c3825866683a6fdd18746cb58",
            "https://github.com/jenniferlu717/Bracken/blob/"
            "cfeac04b6445c44c3825866683a6fdd18746cb58/src/est_abundance.py",
        ),
    }
    _TABLE_EXTS = set(TABLE_EXTENSIONS)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "file": (
                    "FILE",
                    {
                        "label": "Table file",
                        "description": (
                            "BED, bedGraph, GFF, narrowPeak, Kraken report, "
                            "Salmon quant.sf, CSV, TSV, or TXT"
                        ),
                    },
                ),
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
        validation = validate_regular_file(inputs.get("file"), extensions=TABLE_EXTENSIONS, label="Table file")
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
            header, selected = _header_and_rows(reader, source.suffix.lower(), rows_limit)
        has_more = len(selected) > rows_limit
        body = selected[:rows_limit]

        thead = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
        body_html = "".join("<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>" for row in body)
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

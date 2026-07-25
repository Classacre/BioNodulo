"""Parser for documented NCBI BLAST JSON2 and XML2 result artifacts."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import (
    NCBI_BLAST_DOCUMENTATION_URL,
    NCBI_BLAST_URL_API_SHA256,
    node_output_dir,
)


BLAST_PARSE_INPUT_FORMATS = ("auto", "JSON2", "XML2")
BLAST_PARSE_OUTPUT_FORMATS = ("TSV", "JSON")
BLAST_HIT_FIELDS = (
    "query",
    "subject_id",
    "subject_title",
    "scientific_name",
    "percent_identity",
    "evalue",
    "bit_score",
    "alignment_length",
    "query_from",
    "query_to",
    "subject_from",
    "subject_to",
)


def clean_text(value: Any) -> str:
    return str(value or "").replace("\t", " ").replace("\n", " ").strip()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any) -> int | str:
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def percent_identity(identity: Any, alignment_length: Any) -> float:
    length = as_float(alignment_length)
    if length <= 0:
        return 0.0
    return round((as_float(identity) / length) * 100.0, 2)


def first_value(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) not in (None, ""):
            return mapping[key]
    return ""


def parse_json2_hits(raw_results: str) -> list[dict[str, Any]]:
    payload = json.loads(raw_results)
    output = payload.get("BlastOutput2") if isinstance(payload, dict) else payload
    if not isinstance(output, list):
        raise ValueError("BLAST JSON2 results must contain a BlastOutput2 list")

    rows: list[dict[str, Any]] = []
    for record in output:
        if not isinstance(record, dict):
            continue
        report = record.get("report", {})
        results = report.get("results", {}) if isinstance(report, dict) else {}
        search = results.get("search", {}) if isinstance(results, dict) else {}
        if not isinstance(search, dict):
            continue
        query = clean_text(search.get("query_title") or search.get("query_id"))
        hits = search.get("hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            descriptions = hit.get("description", [])
            description = descriptions[0] if descriptions and isinstance(descriptions[0], dict) else {}
            hsps = hit.get("hsps", [])
            hsp = hsps[0] if hsps and isinstance(hsps[0], dict) else {}
            alignment_length = as_int(first_value(hsp, "align_len", "align-len"))
            rows.append(
                {
                    "query": query,
                    "subject_id": clean_text(description.get("id") or hit.get("id")),
                    "subject_title": clean_text(description.get("title") or hit.get("title")),
                    "scientific_name": clean_text(description.get("sciname")),
                    "percent_identity": percent_identity(hsp.get("identity"), alignment_length),
                    "evalue": first_value(hsp, "evalue"),
                    "bit_score": first_value(hsp, "bit_score", "bit-score"),
                    "alignment_length": alignment_length,
                    "query_from": as_int(first_value(hsp, "query_from", "query-from")),
                    "query_to": as_int(first_value(hsp, "query_to", "query-to")),
                    "subject_from": as_int(first_value(hsp, "hit_from", "hit-from")),
                    "subject_to": as_int(first_value(hsp, "hit_to", "hit-to")),
                }
            )
    return rows


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str) -> ET.Element | None:
    return next((item for item in element if local_name(item) == name), None)


def child_text(element: ET.Element | None, name: str) -> str:
    if element is None:
        return ""
    found = child(element, name)
    return clean_text(found.text if found is not None else "")


def parse_xml2_hits(raw_results: str) -> list[dict[str, Any]]:
    root = ET.fromstring(raw_results)
    searches = [element for element in root.iter() if local_name(element) == "Search"]
    if not searches:
        return parse_legacy_xml_hits(root)

    rows: list[dict[str, Any]] = []
    for search in searches:
        query = child_text(search, "query-title") or child_text(search, "query-id")
        hits = child(search, "hits")
        if hits is None:
            continue
        for hit in (item for item in hits if local_name(item) == "Hit"):
            description_container = child(hit, "description")
            description = (
                next(
                    (item for item in description_container if local_name(item) == "HitDescr"),
                    None,
                )
                if description_container is not None
                else None
            )
            hsps = child(hit, "hsps")
            hsp = next((item for item in hsps if local_name(item) == "Hsp"), None) if hsps is not None else None
            alignment_length = as_int(child_text(hsp, "align-len"))
            rows.append(
                {
                    "query": query,
                    "subject_id": child_text(description, "id"),
                    "subject_title": child_text(description, "title"),
                    "scientific_name": child_text(description, "sciname"),
                    "percent_identity": percent_identity(child_text(hsp, "identity"), alignment_length),
                    "evalue": child_text(hsp, "evalue"),
                    "bit_score": as_float(child_text(hsp, "bit-score")),
                    "alignment_length": alignment_length,
                    "query_from": as_int(child_text(hsp, "query-from")),
                    "query_to": as_int(child_text(hsp, "query-to")),
                    "subject_from": as_int(child_text(hsp, "hit-from")),
                    "subject_to": as_int(child_text(hsp, "hit-to")),
                }
            )
    return rows


def parse_legacy_xml_hits(root: ET.Element) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for iteration in (element for element in root.iter() if local_name(element) == "Iteration"):
        query = child_text(iteration, "Iteration_query-def") or child_text(iteration, "Iteration_query-ID")
        hits = child(iteration, "Iteration_hits")
        if hits is None:
            continue
        for hit in (item for item in hits if local_name(item) == "Hit"):
            hsps = child(hit, "Hit_hsps")
            hsp = next((item for item in hsps if local_name(item) == "Hsp"), None) if hsps is not None else None
            alignment_length = as_int(child_text(hsp, "Hsp_align-len"))
            rows.append(
                {
                    "query": query,
                    "subject_id": child_text(hit, "Hit_id"),
                    "subject_title": child_text(hit, "Hit_def"),
                    "scientific_name": "",
                    "percent_identity": percent_identity(child_text(hsp, "Hsp_identity"), alignment_length),
                    "evalue": child_text(hsp, "Hsp_evalue"),
                    "bit_score": as_float(child_text(hsp, "Hsp_bit-score")),
                    "alignment_length": alignment_length,
                    "query_from": as_int(child_text(hsp, "Hsp_query-from")),
                    "query_to": as_int(child_text(hsp, "Hsp_query-to")),
                    "subject_from": as_int(child_text(hsp, "Hsp_hit-from")),
                    "subject_to": as_int(child_text(hsp, "Hsp_hit-to")),
                }
            )
    return rows


def detect_input_format(path: Path, requested: str) -> str:
    if requested != "auto":
        if requested not in {"JSON2", "XML2"}:
            raise ValueError(f"Unsupported BLAST parse input_format: {requested}")
        return requested
    if path.suffix.lower() == ".xml":
        return "XML2"
    if path.suffix.lower() == ".json":
        return "JSON2"
    return "XML2" if path.read_text(encoding="utf-8", errors="replace").lstrip().startswith("<") else "JSON2"


def write_tsv(path: Path, hits: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BLAST_HIT_FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for hit in hits:
            row = {field: clean_text(hit.get(field, "")) for field in BLAST_HIT_FIELDS}
            row["percent_identity"] = f"{as_float(hit.get('percent_identity')):.2f}"
            writer.writerow(row)


class NCBIBLASTParseNode(BaseNode):
    """Convert saved BLAST JSON2 or XML2 output to a compact hit table."""

    NODE_ID = "ncbi_blast_parse"
    DISPLAY_NAME = "NCBI BLAST Parse"
    CATEGORY = "databases"
    DESCRIPTION = "Parse saved NCBI BLAST JSON2 or XML2 output into top-hit records."
    SEARCH_ALIASES = ["ncbi", "blast", "parse", "hits", "alignment", "json2", "xml2"]
    RETURN_TYPES = ("FILE", "JSON")
    RETURN_NAMES = ("parsed_hits", "parse_summary")
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "Common URL API 2026-07-19 snapshot"
    DOCUMENTATION_URL = NCBI_BLAST_DOCUMENTATION_URL
    SOURCE_URL = NCBI_BLAST_DOCUMENTATION_URL
    SOURCE_SHA256 = NCBI_BLAST_URL_API_SHA256
    UPSTREAM_SOURCE = "Common URL API JSON2 and XML2 report schemas"
    EXIT_SEMANTICS = "Missing, malformed, or unsupported result artifacts fail without partial output."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "blast_results": ("FILE", {"description": "Saved BLAST JSON2 or XML2 result file"}),
            },
            "optional": {
                "input_format": (list(BLAST_PARSE_INPUT_FORMATS), {"default": "auto"}),
                "output_format": (list(BLAST_PARSE_OUTPUT_FORMATS), {"default": "TSV"}),
                "max_hits": ("INT", {"default": 50, "min": 1}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        source = Path(str(kwargs.get("blast_results", ""))).expanduser()
        if not source.is_file():
            raise ValueError(f"BLAST results file does not exist: {source}")
        input_format = detect_input_format(
            source,
            str(kwargs.get("input_format", "auto") or "auto"),
        )
        output_format = str(kwargs.get("output_format", "TSV") or "TSV").upper()
        if output_format not in BLAST_PARSE_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported BLAST parse output_format: {output_format}")
        max_hits = kwargs.get("max_hits", 50)
        if isinstance(max_hits, bool) or not isinstance(max_hits, int) or max_hits < 1:
            raise ValueError("max_hits must be an integer of at least 1")

        raw_results = source.read_text(encoding="utf-8")
        all_hits = parse_json2_hits(raw_results) if input_format == "JSON2" else parse_xml2_hits(raw_results)
        parsed_hits = all_hits[:max_hits]
        output_dir = node_output_dir(self, context)
        hits_path = output_dir / ("blast_hits.json" if output_format == "JSON" else "blast_hits.tsv")
        if output_format == "JSON":
            hits_path.write_text(json.dumps(parsed_hits, indent=2), encoding="utf-8")
        else:
            write_tsv(hits_path, parsed_hits)

        summary = {
            "input_format": input_format,
            "output_format": output_format,
            "source_path": str(source),
            "parsed_hits_path": str(hits_path),
            "parsed_hit_count": len(parsed_hits),
            "available_hit_count": len(all_hits),
            "queries": sorted({str(hit["query"]) for hit in all_hits if hit.get("query")}),
        }
        summary_path = output_dir / "blast_parse_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return {
            "outputs": {
                "parsed_hits": str(hits_path),
                "parse_summary": str(summary_path),
            }
        }

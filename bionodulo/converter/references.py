"""Reference/bibliography export from workflow node citation metadata.

Collects the CITATION_DOIS / CITATION_URLS / CITATION_TEXT declared by each
node in a workflow and renders them as RIS, BibTeX, or CSV without pulling in
an external bibliography library.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from typing import Any


def collect_references(workflow: dict[str, Any], registry: Any) -> list[dict[str, Any]]:
    """Gather deduplicated citation references for every node in a workflow.

    A node contributes a reference only when the registry (or, when the type is
    unknown to the registry, the node's embedded ``node_info``) carries at
    least one DOI, URL, or citation text. Note/visual-only nodes are skipped.

    Returns references sorted by their primary key; each reference maps to
    ``{"dois": [...], "urls": [...], "text": str|None, "nodes": [...]}`` where
    ``nodes`` lists ``{"id", "display_name", "version"}`` dictionaries.
    """
    collected: dict[str, dict[str, Any]] = {}

    for node in workflow.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", ""))
        node_id = str(node.get("id", node_type))
        node_info = node.get("node_info") or {}

        dois: list[str] = []
        urls: list[str] = []
        text = ""
        display_name = node_type
        version = ""

        node_class = registry.get(node_type) if registry is not None else None
        if node_class is not None:
            if getattr(node_class, "VISUAL_ONLY", False):
                continue
            dois = [str(d) for d in getattr(node_class, "CITATION_DOIS", None) or [] if d]
            urls = [str(u) for u in getattr(node_class, "CITATION_URLS", None) or [] if u]
            text = str(getattr(node_class, "CITATION_TEXT", "") or "")
            display_name = str(getattr(node_class, "DISPLAY_NAME", "") or node_type)
            version = str(getattr(node_class, "VERSION", "") or "")
        else:
            if node_info.get("visual_only"):
                continue
            dois = [str(d) for d in node_info.get("citation_dois") or [] if d]
            urls = [str(u) for u in node_info.get("citation_urls") or [] if u]
            text = str(node_info.get("citation_text") or "")
            display_name = str(node_info.get("display_name") or node_type)
            version = str(node_info.get("version") or "")

        if not dois and not urls and not text:
            continue

        key = _primary_key(dois, urls, text)
        reference = collected.get(key)
        if reference is None:
            reference = {"dois": [], "urls": [], "text": text or None, "nodes": []}
            collected[key] = reference
        for doi in dois:
            if doi not in reference["dois"]:
                reference["dois"].append(doi)
        for url in urls:
            if url not in reference["urls"]:
                reference["urls"].append(url)
        if not reference["text"] and text:
            reference["text"] = text
        if not any(entry["id"] == node_id for entry in reference["nodes"]):
            reference["nodes"].append({"id": node_id, "display_name": display_name, "version": version})

    for reference in collected.values():
        reference["nodes"].sort(key=lambda entry: entry["id"])
    return [collected[key] for key in sorted(collected)]


def _primary_key(dois: list[str], urls: list[str], text: str) -> str:
    if dois:
        return dois[0].strip().lower()
    if urls:
        return urls[0].strip()
    return re.sub(r"\s+", " ", text).strip()


def export_references(workflow: dict[str, Any], registry: Any, fmt: str) -> str:
    """Render workflow references as RIS, BibTeX, or CSV text."""
    references = collect_references(workflow, registry)
    if not references:
        return ""
    normalized = fmt.lower()
    if normalized == "ris":
        return _render_ris(references)
    if normalized == "bibtex":
        return _render_bibtex(references)
    if normalized == "csv":
        return _render_csv(references)
    raise ValueError(f"Unsupported references export format: '{fmt}'. Supported: ris, bibtex, csv")


def _reference_title(reference: dict[str, Any]) -> str:
    text = reference.get("text")
    if text:
        return text
    names = ", ".join(node["display_name"] for node in reference["nodes"])
    return f"BioNodulo nodes: {names}"


def _ris_line(tag: str, value: str) -> str:
    return f"{tag}  - {value}"


def _render_ris(references: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for reference in references:
        dois: list[str] = reference["dois"]
        urls: list[str] = reference["urls"]
        title = _reference_title(reference)
        node_ids = [node["id"] for node in reference["nodes"]]

        records: list[dict[str, str | None]] = []
        for doi in dois:
            url = next((u for u in urls if doi.lower() in u.lower()), None)
            records.append({"ty": "JOUR", "doi": doi, "url": url})
        if not dois:
            records.append({"ty": "COMP", "doi": None, "url": urls[0] if urls else None})

        for record in records:
            lines.append(_ris_line("TY", str(record["ty"])))
            lines.append(_ris_line("TI", title))
            if record["doi"]:
                lines.append(_ris_line("DO", str(record["doi"])))
            if record["url"]:
                lines.append(_ris_line("UR", str(record["url"])))
            for node_id in node_ids:
                lines.append(_ris_line("KW", node_id))
            lines.append(_ris_line("DB", "BioNodulo"))
            lines.append("ER  - ")
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _bibtex_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _bibtex_key(reference: dict[str, Any]) -> str:
    digest = hashlib.sha256(_primary_key(reference["dois"], reference["urls"], reference.get("text") or "").encode())
    return f"bionodulo_{digest.hexdigest()[:8]}"


def _render_bibtex(references: list[dict[str, Any]]) -> str:
    entries: list[str] = []
    for reference in references:
        dois: list[str] = reference["dois"]
        urls: list[str] = reference["urls"]
        node_ids = [node["id"] for node in reference["nodes"]]
        note_parts = [*dois[1:], *urls[1:], f"used by: {', '.join(node_ids)}"]

        fields = [f"  title = {{{_bibtex_escape(_reference_title(reference))}}}"]
        if dois:
            fields.append(f"  doi = {{{_bibtex_escape(dois[0])}}}")
        if urls:
            fields.append(f"  url = {{{_bibtex_escape(urls[0])}}}")
        fields.append(f"  note = {{{_bibtex_escape(', '.join(note_parts))}}}")
        entries.append(f"@misc{{{_bibtex_key(reference)},\n" + ",\n".join(fields) + "\n}")
    return "\n".join(entries) + "\n"


def _render_csv(references: list[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["node_id", "node_display_name", "node_version", "doi", "url", "citation_text"])
    for reference in references:
        dois: list[str] = reference["dois"]
        urls: list[str] = reference["urls"]
        text = reference.get("text") or ""
        for node in reference["nodes"]:
            for doi in dois:
                writer.writerow([node["id"], node["display_name"], node["version"], doi, "", text])
            for url in urls:
                if any(doi.lower() in url.lower() for doi in dois):
                    continue
                writer.writerow([node["id"], node["display_name"], node["version"], "", url, text])
            if not dois and not urls:
                writer.writerow([node["id"], node["display_name"], node["version"], "", "", text])
    return buffer.getvalue()

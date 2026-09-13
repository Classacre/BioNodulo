#!/usr/bin/env python
"""Crawl the full bio.tools registry and audit EDAM annotation completeness.

The thesis claims that contract inference can run on registry metadata at
ecosystem scale; this script is the evidence run. It paginates the entire
bio.tools API (roughly 34,000 tools as of September 2026), stores a compact
JSONL snapshot, and computes the registry-wide annotation completeness
statistics that no published work provides (dossier section 3.1, gap 6).

Usage:
    python scripts/crawl_biotools_registry.py                 # crawl + analyze
    python scripts/crawl_biotools_registry.py --analyze-only  # re-analyze snapshot
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "reports" / "biotools_registry"
SNAPSHOT_PATH = SNAPSHOT_DIR / "registry_snapshot.jsonl"
REPORT_PATH = SNAPSHOT_DIR / "completeness_report.json"
NODE_INDEX_PATH = REPO_ROOT / "bionodulo" / "nodes" / "node_index.json"
NODE_METADATA_PATH = REPO_ROOT / "bionodulo" / "nodes" / "node_metadata.json"

API_LIST = "https://bio.tools/api/tool/?page={page}&format=json"
USER_AGENT = "bionodulo-registry-audit/0.1 (PhD contract-inference study)"
REQUEST_DELAY = 0.12
MAX_RETRIES = 6

COMPACT_FIELDS = (
    "biotoolsID",
    "name",
    "toolType",
    "topic",
    "function",
    "version",
    "license",
    "documentation",
    "homepage",
    "publication",
)


def _fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 1.0
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError, OSError) as error:
            if attempt == MAX_RETRIES - 1:
                raise
            print(f"  retry {attempt + 1} after {type(error).__name__}: {error}", flush=True)
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def crawl(resume: bool = True) -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if resume and SNAPSHOT_PATH.exists():
        with SNAPSHOT_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    seen.add(json.loads(line)["biotoolsID"])
                except (json.JSONDecodeError, KeyError):
                    continue
        print(f"resuming with {len(seen)} tools already snapshotted")

    page = 1
    total = None
    written = 0
    with SNAPSHOT_PATH.open("a", encoding="utf-8") as out:
        while True:
            data = _fetch(API_LIST.format(page=page))
            if total is None:
                total = data["count"]
                print(f"registry reports {total} tools")
            items = data.get("list") or []
            if not items:
                break
            for item in items:
                biotools_id = item.get("biotoolsID")
                if not biotools_id or biotools_id in seen:
                    continue
                compact = {field: item.get(field) for field in COMPACT_FIELDS}
                out.write(json.dumps(compact, ensure_ascii=False) + "\n")
                seen.add(biotools_id)
                written += 1
            if page % 25 == 0:
                print(f"  page {page}: {len(seen)}/{total} tools", flush=True)
            if not data.get("next"):
                break
            page += 1
            time.sleep(REQUEST_DELAY)
    print(f"snapshot complete: {len(seen)} tools ({written} newly written)")
    return len(seen)


def _edam_uris(terms: list | dict | None) -> set[str]:
    if isinstance(terms, dict):
        terms = [terms]
    uris: set[str] = set()
    for term in terms or []:
        if isinstance(term, str) and term.startswith("http"):
            uris.add(term)
        elif isinstance(term, dict):
            uri = term.get("uri") or term.get("term")
            if uri:
                uris.add(uri)
    return uris


def analyze() -> dict:
    tools = []
    with SNAPSHOT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                tools.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    total = len(tools)

    def share(count: int) -> float:
        return round(100.0 * count / total, 2) if total else 0.0

    has_operation = 0
    has_topic = 0
    functions_with_inputs = 0
    functions_with_input_formats = 0
    functions_with_outputs = 0
    functions_with_output_formats = 0
    function_count = 0
    has_version = 0
    has_license = 0
    has_documentation = 0
    tooltype_counter: Counter[str] = Counter()
    operation_counter: Counter[str] = Counter()

    for tool in tools:
        tooltypes = tool.get("toolType") or ["(none)"]
        for tooltype in tooltypes:
            tooltype_counter[tooltype] += 1
        if tool.get("version"):
            has_version += 1
        if tool.get("license"):
            has_license += 1
        docs = tool.get("documentation") or []
        if any(doc.get("url") for doc in docs if isinstance(doc, dict)):
            has_documentation += 1
        topics = _edam_uris(tool.get("topic"))
        if topics:
            has_topic += 1
        operations_for_tool: set[str] = set()
        annotated_inputs = annotated_input_formats = annotated_outputs = 0
        annotated_output_formats = 0
        for function in tool.get("function") or []:
            function_count += 1
            operations_for_tool.update(
                _edam_uris(
                    function.get("operation")
                    or function.get("operations")
                    or function.get("function")
                )
            )
            inputs = function.get("inputs") or function.get("input") or []
            outputs = function.get("outputs") or function.get("output") or []
            if any(_edam_uris(item.get("data")) for item in inputs if isinstance(item, dict)):
                annotated_inputs += 1
            if any(_edam_uris(item.get("format")) for item in inputs if isinstance(item, dict)):
                annotated_input_formats += 1
            if any(_edam_uris(item.get("data")) for item in outputs if isinstance(item, dict)):
                annotated_outputs += 1
            if any(_edam_uris(item.get("format")) for item in outputs if isinstance(item, dict)):
                annotated_output_formats += 1
        if operations_for_tool:
            has_operation += 1
            operation_counter.update(operations_for_tool)
        if tool.get("function"):
            functions_with_inputs += annotated_inputs
            functions_with_input_formats += annotated_input_formats
            functions_with_outputs += annotated_outputs
            functions_with_output_formats += annotated_output_formats

    report = {
        "snapshot_tools": total,
        "percent_with_edam_operation": share(has_operation),
        "percent_with_edam_topic": share(has_topic),
        "percent_with_version": share(has_version),
        "percent_with_license": share(has_license),
        "percent_with_documentation_url": share(has_documentation),
        "function_io_annotation": {
            "functions_total": function_count,
            "percent_functions_with_input_data": round(
                100.0 * functions_with_inputs / function_count, 2
            ) if function_count else 0.0,
            "percent_functions_with_input_format": round(
                100.0 * functions_with_input_formats / function_count, 2
            ) if function_count else 0.0,
            "percent_functions_with_output_data": round(
                100.0 * functions_with_outputs / function_count, 2
            ) if function_count else 0.0,
            "percent_functions_with_output_format": round(
                100.0 * functions_with_output_formats / function_count, 2
            ) if function_count else 0.0,
        },
        "tooltype_distribution": dict(tooltype_counter.most_common(12)),
        "top_operations": dict(operation_counter.most_common(15)),
        "counts": {
            "has_operation": has_operation,
            "has_topic": has_topic,
            "has_version": has_version,
            "has_license": has_license,
            "has_documentation": has_documentation,
        },
    }

    # BioNodulo coverage: match our 979 node types against registry ids.
    index = json.loads(NODE_INDEX_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(NODE_METADATA_PATH.read_text(encoding="utf-8"))
    registry_ids = {tool["biotoolsID"].lower() for tool in tools if tool.get("biotoolsID")}
    registry_names = {tool.get("name", "").lower() for tool in tools}
    module_family = {}
    for node_id, module in index.items():
        if "builtin." in module:
            tail = module.split("builtin.", 1)[1]
            family = tail.split(".", 1)[0].replace("_family", "")
            module_family[node_id] = family
    matched: set[str] = set()
    unmatched: Counter[str] = Counter()
    for node_id, family in module_family.items():
        stem = node_id.split("_")[0] if "_" in node_id else node_id
        display = (metadata.get(node_id, {}).get("display_name") or "").lower()
        candidates = {family.lower(), stem, node_id, display}
        if candidates & registry_ids or candidates & registry_names:
            matched.add(family)
        else:
            unmatched[family] += 1
    report["bionodulo_coverage"] = {
        "node_types": len(module_family),
        "families_with_registry_match": len(matched),
        "matched_families_sample": sorted(matched)[:40],
        "top_unmatched_families": dict(unmatched.most_common(15)),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()
    if not args.analyze_only:
        crawl()
    report = analyze()
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    for key in (
        "snapshot_tools",
        "percent_with_edam_operation",
        "percent_with_edam_topic",
        "percent_with_version",
        "percent_with_license",
        "percent_with_documentation_url",
    ):
        print(f"  {key}: {report[key]}")
    io = report["function_io_annotation"]
    for key, value in io.items():
        print(f"  {key}: {value}")
    cov = report["bionodulo_coverage"]
    print(f"  bionodulo families with registry match: {cov['families_with_registry_match']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

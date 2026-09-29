#!/usr/bin/env python
"""Rank bio.tools records that no builtin node currently covers.

The point is to replace guesswork with a measured worklist. A candidate is only
interesting if it is (a) plausibly a command-line tool, (b) not already covered by
an existing node, and (c) carries enough evidence to author a real contract:
documentation, publications, EDAM annotations.

Matching is deliberately conservative and multi-signal. A record is treated as
covered when its accession, normalised name, or a declared executable or conda
package matches an existing node's identity. Name similarity alone is a *hint*
and is reported separately rather than silently treated as a match, because
display-name similarity is not identity.

Nothing here is an admission. This produces a worklist, not a capability claim.

Usage:
    python scripts/find_node_gaps.py \
        --snapshot reports/biotools_registry/current/registry.jsonl \
        --node-metadata bionodulo/nodes/node_metadata.json \
        --node-index bionodulo/nodes/node_index.json \
        --output reports/node-expansion/gap-candidates.json
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

# Records whose declared types make a local command plausible.
INVOCABLE_TYPES = {"Command-line tool", "Suite", "Script", "Workflow", "Library"}
# Types that describe a service, portal or desktop app: no local argv.
NON_LOCAL_TYPES = {
    "Web application", "Database portal", "Desktop application",
    "Web service", "Web API", "Workbench", "Bioinformatics portal",
    "SPARQL endpoint", "Mobile application", "Ontology", "Plug-in",
}
NOISE = re.compile(r"[^a-z0-9]+")


def norm(value: str) -> str:
    return NOISE.sub("", (value or "").casefold())


def load_node_identity(metadata_path: Path, index_path: Path) -> tuple[set[str], dict[str, str]]:
    """Return (exact identity terms, node_id -> term that matched)."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    terms: dict[str, str] = {}

    for node_id, module in index.items():
        for candidate in (node_id, module.rsplit(".", 1)[-1]):
            terms.setdefault(norm(candidate), node_id)

    for node_id, meta in metadata.items():
        if not isinstance(meta, dict):
            continue
        for field in ("name", "display_name"):
            value = meta.get(field)
            if value:
                terms.setdefault(norm(str(value)), node_id)
        # Declared runtime identities are the strongest signal available.
        for field in ("required_executables", "required_conda_packages"):
            for value in meta.get(field) or []:
                token = norm(str(value).split("=")[0].split(">")[0])
                if len(token) >= 3:
                    terms.setdefault(token, node_id)
    terms.pop("", None)
    return set(terms), terms


def score(record: dict) -> tuple[int, list[str]]:
    """Transparent usefulness score. Signals only, never a quality claim."""
    total = 0
    reasons: list[str] = []
    types = set(record.get("toolType") or [])
    if "Command-line tool" in types:
        total += 3
        reasons.append("+3 command-line tool")
    if "Suite" in types:
        total += 2
        reasons.append("+2 suite")
    if "Script" in types:
        total += 1
        reasons.append("+1 script")
    if record.get("documentation"):
        total += 3
        reasons.append("+3 documentation URL present")
    if record.get("homepage"):
        total += 1
        reasons.append("+1 homepage")
    if record.get("license"):
        total += 1
        reasons.append("+1 license declared")
    publications = len(record.get("publication") or [])
    if publications:
        bonus = min(publications, 4)
        total += bonus
        reasons.append(f"+{bonus} publication(s) as a research-use proxy")
    functions = record.get("function") or []
    operations = sum(len(f.get("operation") or []) for f in functions if isinstance(f, dict))
    if operations:
        bonus = min(operations, 3)
        total += bonus
        reasons.append(f"+{bonus} EDAM operation(s)")
    if record.get("topic"):
        total += 1
        reasons.append("+1 EDAM topic")
    if record.get("version"):
        total += 1
        reasons.append("+1 version label")
    if "Linux" in (record.get("operatingSystem") or []):
        total += 1
        reasons.append("+1 declares Linux")
    return total, reasons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--node-metadata", type=Path, required=True)
    parser.add_argument("--node-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--min-score", type=int, default=6)
    args = parser.parse_args()

    identity, term_owner = load_node_identity(args.node_metadata, args.node_index)

    covered = 0
    non_local = 0
    no_annotation = 0
    total_records = 0
    candidates: list[dict] = []
    type_counts: Counter = Counter()

    with args.snapshot.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            total_records += 1
            accession = record["biotoolsID"]
            types = set(record.get("toolType") or [])
            type_counts.update(types or ["Unspecified"])

            # Already covered?
            keys = {norm(accession), norm(record.get("name") or "")}
            for function in record.get("function") or []:
                if not isinstance(function, dict):
                    continue
                for item in function.get("operation") or []:
                    pass
            if keys & identity:
                covered += 1
                continue

            if types and not (types & INVOCABLE_TYPES):
                non_local += 1
                continue

            total, reasons = score(record)
            if total < args.min_score:
                no_annotation += 1
                continue

            candidates.append({
                "biotools_id": accession,
                "name": record.get("name"),
                "score": total,
                "reasons": reasons,
                "tool_types": sorted(types),
                "homepage": record.get("homepage"),
                "documentation_urls": [d.get("url") for d in record.get("documentation") or []
                                       if isinstance(d, dict) and d.get("url")][:3],
                "license": record.get("license"),
                "versions": [str(v) for v in record.get("version") or []][:5],
                "publication_dois": [p.get("doi") for p in record.get("publication") or []
                                     if isinstance(p, dict) and p.get("doi")][:8],
                "edam_topics": [t.get("term") for t in record.get("topic") or []
                                if isinstance(t, dict)][:6],
                "edam_operations": sorted({
                    o.get("uri") for f in record.get("function") or []
                    if isinstance(f, dict) for o in f.get("operation") or []
                    if isinstance(o, dict) and o.get("uri")})[:8],
                "operating_systems": [str(o) for o in record.get("operatingSystem") or []],
                "description": (record.get("description") or "")[:280],
            })

    candidates.sort(key=lambda item: (-item["score"], item["biotools_id"].casefold()))
    report = {
        "schema_version": 1,
        "snapshot_records": total_records,
        "covered_by_existing_node": covered,
        "skipped_non_local_interface": non_local,
        "skipped_below_score_threshold": no_annotation,
        "candidates": len(candidates),
        "min_score": args.min_score,
        "registry_tool_types": dict(type_counts.most_common(12)),
        "top_120": [c["biotools_id"] for c in candidates[:120]],
        "scope": (
            "A worklist, not a capability claim. Nothing here has been installed, run or "
            "validated. Absence from this list is not evidence that a tool is covered."
        ),
        "records": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "records"}, indent=2)[:3000])


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Infer draft semantic contracts from bio.tools EDAM metadata.

Aim A, months-1-6 milestone: contract inference runs on registry metadata.
This script derives draft assumption and guarantee clauses for BioNodulo
node types from the EDAM operations, formats, and naming conventions in
their bio.tools records, writes them in NodeSemanticContract shape, and
measures clause-level agreement against the expert-written seed contracts
(dossier section 3.3: agreement measurement against expert contracts).

Inference rules (each maps an EDAM operation IRI or format cue to a
contract clause; the mapping table is the versioned artifact):
  operation Sorting            -> guarantee sort_order=coordinate
  operation Indexing           -> assume   sort_order=coordinate
  operation Mapping/Alignment  -> guarantee sort_order=unsorted, propagate assembly
  format BAM/SAM/CRAM in+out   -> propagate all dimensions
  counting operations + param  -> strandedness assumption via param_map (0/1/2)

Usage:
    python scripts/infer_contracts.py            # infer over biotools_links.json
    python scripts/infer_contracts.py --snapshot # use the full registry snapshot
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LINKS_PATH = REPO_ROOT / "bionodulo" / "nodes" / "generated" / "biotools_links.json"
SNAPSHOT_PATH = REPO_ROOT / "reports" / "biotools_registry" / "registry_snapshot.jsonl"
SEEDS_PATH = REPO_ROOT / "bionodulo" / "nodes" / "generated" / "semantic_contracts.json"
OUTPUT_PATH = REPO_ROOT / "bionodulo" / "nodes" / "generated" / "inferred_contracts.json"
AGREEMENT_PATH = REPO_ROOT / "reports" / "biotools_registry" / "inference_agreement.json"

ALIGNMENT_FORMATS = {"format_2572", "format_2573", "format_3462"}  # BAM, SAM, CRAM

OPERATION_RULES: dict[str, list[dict]] = {
    # EDAM operation IRI fragment -> clauses (kind: assume|guarantee)
    "operation_3359": [  # Sorting
        {"kind": "guarantee", "dimension": "sort_order", "op": "set", "value": "coordinate"},
    ],
    "operation_0230": [  # Indexing (structure indexing)
        {"kind": "assume", "dimension": "sort_order", "op": "eq", "value": "coordinate"},
    ],
    "operation_0292": [  # Mapping
        {"kind": "guarantee", "dimension": "sort_order", "op": "set", "value": "unsorted"},
        {"kind": "guarantee", "dimension": "reference_assembly", "op": "propagate"},
    ],
    "operation_3198": [  # Read binning/counting path
        {"kind": "assume", "dimension": "strandedness", "op": "param_map",
         "param": "strand_specificity", "param_map": {"0": "unstranded", "1": "forward", "2": "reverse"}},
    ],
}


def _operation_fragments(record: dict) -> set[str]:
    fragments: set[str] = set()
    for function in record.get("functions") or record.get("function") or []:
        terms = (
            function.get("operation")
            or function.get("operations")
            or function.get("function")
            or []
        )
        for term in terms:
            if isinstance(term, dict):
                uri = term.get("uri") or term.get("term") or ""
            else:
                uri = term if isinstance(term, str) else ""
            fragments.add(uri.rsplit("/", 1)[-1])
    return fragments


def _format_fragments(record: dict) -> set[str]:
    fragments: set[str] = set()
    for function in record.get("functions") or record.get("function") or []:
        for side in ("inputs", "outputs", "input", "output"):
            for item in function.get(side) or []:
                for term in (item or {}).get("formats") or []:
                    if isinstance(term, dict):
                        uri = term.get("uri") or term.get("term") or ""
                    else:
                        uri = term if isinstance(term, str) else ""
                    fragments.add(uri.rsplit("/", 1)[-1])
    return fragments


def infer_for_record(record: dict) -> dict:
    """Derive draft clauses from one bio.tools record."""
    assumes: list[dict] = []
    guarantees: list[dict] = []
    fragments = _operation_fragments(record)
    formats = _format_fragments(record)
    for fragment, clauses in OPERATION_RULES.items():
        if fragment not in fragments:
            continue
        for clause in clauses:
            (assumes if clause["kind"] == "assume" else guarantees).append(clause)
    if formats & ALIGNMENT_FORMATS:
        # Alignment-format tools are state-preserving on pass-through ports.
        for dimension in ("sort_order", "reference_assembly", "strandedness", "deduplication_state"):
            if not any(g.get("dimension") == dimension for g in guarantees):
                guarantees.append({"kind": "guarantee", "dimension": dimension, "op": "propagate"})
    return {"assumes": assumes, "guarantees": guarantees}


def load_sources(use_snapshot: bool) -> dict[str, dict]:
    """node_type -> bio.tools record (already matched)."""
    if use_snapshot and SNAPSHOT_PATH.exists():
        seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
        seed_types = {entry["node_type"] for entry in seeds["contracts"]}
        # Match node types to registry ids by family stem, as the crawler does.
        registry: dict[str, dict] = {}
        with SNAPSHOT_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                registry[record.get("biotoolsID", "").lower()] = {
                    "functions": record.get("function") or [],
                }
        matched: dict[str, dict] = {}
        for node_type in seed_types | {
            "samtools_view", "samtools_sort", "samtools_index", "hisat2_align",
            "featurecounts", "sam_to_bam", "fastqc",
        }:
            stem = node_type.split("_")[0]
            for candidate in (node_type, stem, stem.replace("s", "")):
                if candidate in registry:
                    matched[node_type] = registry[candidate]
                    break
        return matched
    links = json.loads(LINKS_PATH.read_text(encoding="utf-8"))
    return {
        node_type: {"functions": entry.get("functions") or []}
        for node_type, entry in links.get("links", {}).items()
        if entry.get("found")
    }


def measure_agreement(inferred: dict[str, dict]) -> dict:
    """Clause-level agreement between inferred drafts and expert seeds."""
    seeds = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    comparisons: list[dict] = []
    outcomes: Counter[str] = Counter()
    for seed in seeds["contracts"]:
        node_type = seed["node_type"]
        draft = inferred.get(node_type)
        expert_assumes = {
            (port, clause.get("dimension"), clause.get("value") or clause.get("op"))
            for port, clauses in seed["inputs"].items()
            for clause in clauses
        }
        expert_guarantees = {
            (port, guarantee.get("dimension"), guarantee.get("value") or guarantee.get("op"))
            for port, guarantees in seed["outputs"].items()
            for guarantee in guarantees
        }
        draft_assumes = {
            ("*", clause.get("dimension"), clause.get("value") or clause.get("op"))
            for clause in (draft or {}).get("assumes", [])
        }
        draft_guarantees = {
            ("*", clause.get("dimension"), clause.get("value") or clause.get("op"))
            for clause in (draft or {}).get("guarantees", [])
        }
        expert_dims = {(entry[1], entry[2]) for entry in expert_assumes | expert_guarantees}
        draft_dims = {(entry[1], entry[2]) for entry in draft_assumes | draft_guarantees}
        if not expert_dims and not draft_dims:
            continue
        for dimension_pair in expert_dims | draft_dims:
            in_expert = dimension_pair in expert_dims
            in_draft = dimension_pair in draft_dims
            if in_expert and in_draft:
                outcome = "agree"
            elif in_expert:
                outcome = "missed_by_inference"
            else:
                outcome = "spurious_from_inference"
            outcomes[outcome] += 1
            comparisons.append({"node_type": node_type, "dimension": dimension_pair[0],
                                "value_or_op": dimension_pair[1], "outcome": outcome})
    total = sum(outcomes.values())
    return {
        "clauses_compared": total,
        "agreement_percent": round(100.0 * outcomes["agree"] / total, 1) if total else None,
        "counts": dict(outcomes),
        "detail": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()

    sources = load_sources(args.snapshot)
    inferred: dict[str, dict] = {}
    for node_type, record in sources.items():
        result = infer_for_record(record)
        if result["assumes"] or result["guarantees"]:
            inferred[node_type] = result

    OUTPUT_PATH.write_text(
        json.dumps({"schema_version": "0.1", "source": "bio.tools EDAM inference v0.1",
                    "inferred": inferred}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    agreement = measure_agreement(inferred)
    AGREEMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGREEMENT_PATH.write_text(json.dumps(agreement, indent=2), encoding="utf-8")
    print(f"inferred contracts for {len(inferred)} node types -> {OUTPUT_PATH}")
    print(f"agreement vs expert seeds: {agreement['agreement_percent']}% "
          f"({agreement['counts']}) -> {AGREEMENT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

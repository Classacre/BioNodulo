#!/usr/bin/env python
"""Build the one-record-per-accession builtin-expansion ledger.

Every bio.tools accession in a verified snapshot receives exactly one parent row
with a terminal state. The ledger keeps separate: registry record identity,
interface class, function/EDAM annotation, reconciliation against existing
builtins, and admission disposition.

It never infers executable coverage from metadata. A record with a descriptor
link, a container, a homepage or an EDAM term is still not an installed
environment or a validated run. Unknown facts stay ``null``/``[]``; gaps are
never filled with plausible values.

Parent states (terminal, exactly one per accession):

``reference_only``
    Kept as discovery metadata. Either no machine interface is annotated, or the
    record is covered by an existing builtin, or it is in the unprocessed tail.
``candidate``
    Selected into the prioritized cohort. Unfinished: carries an owner and a
    next step.
``executable_admitted``
    A tested executable operation was admitted from this record, with a real
    queued run and an independent oracle.
``blocked``
    A specific, machine-readable blocker prevents admission.
``retired_or_missing_on_resync``
    The accession disappeared on a later sync.

Blocker codes: ``no_machine_invocation``, ``license_or_access``,
``missing_exact_version``, ``unsupported_descriptor``,
``unsupported_platform``, ``dependency_resolution_failed``,
``reference_data_unavailable``, ``scientific_oracle_missing``.

Usage:
    python scripts/build_expansion_ledger.py \
        --snapshot-dir reports/biotools_registry/current \
        --output-dir reports/biotools_registry/current/ledger \
        --cohort-size 40
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Interface classes. bio.tools tool types are non-exclusive, so a record may
# carry several; classification looks at the whole set.
NON_EXECUTABLE_TYPES = {
    "Web application", "Database portal", "Desktop application",
    "Web service", "Web API", "Workbench",
}
EXECUTABLE_TYPES = {
    "Command-line tool", "Suite", "Script", "Workflow", "Library",
}

# Download/link type labels that carry a machine-readable or reproducible
# artifact. Presence is a *candidate* signal only, never an admission.
#
# These are the literal bio.tools `download.type` values (verified against the
# 2026-09-25 snapshot): the most common are "Source code" (4,649),
# "Software package" (727), "Downloads page" (715), "Screenshot" (609),
# "Binaries" (539) and "Container file" (368). `link.type` is a *list*, so it is
# flattened before matching; its values include "Repository" and "Galaxy
# service".
DESCRIPTOR_TYPES = {
    "tool wrapper (cwl)", "tool wrapper (galaxy)", "tool wrapper (other)",
    "api specification", "command-line specification", "galaxy service",
}
CWL_DESCRIPTOR_TYPES = {"tool wrapper (cwl)"}
CONTAINER_TYPES = {"container file", "vm image"}
PACKAGE_TYPES = {
    "source code", "software package", "binaries", "downloads page",
}

BLOCKER_CODES = {
    "no_machine_invocation", "license_or_access", "missing_exact_version",
    "unsupported_descriptor", "unsupported_platform",
    "dependency_resolution_failed", "reference_data_unavailable",
    "scientific_oracle_missing",
}

RECONCILIATION_STATUSES = {
    "unreviewed", "existing_exact", "existing_related_operation",
    "new_operation", "duplicate_record", "ambiguous", "no_existing_node",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def link_types(record: dict) -> set[str]:
    """Normalized download/link type labels.

    ``download[].type`` is a plain string but ``link[].type`` is a list, so both
    shapes are flattened. Treating the list as a string silently produced
    ``"['repository']"`` and matched nothing.
    """
    labels: set[str] = set()
    for entry in (record.get("download") or []) + (record.get("link") or []):
        if not isinstance(entry, dict):
            continue
        raw = entry.get("type")
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if isinstance(value, str) and value.strip():
                labels.add(value.strip().casefold())
    return labels


def classify_interfaces(tool_types: list[str]) -> tuple[list[str], bool, bool]:
    """Return (declared types, machine_invocable, annotated)."""
    declared = [t for t in tool_types if t]
    if not declared:
        return [], False, False
    invocable = any(t in EXECUTABLE_TYPES for t in declared)
    return declared, invocable, True


def function_rows(record: dict, accession: str, retrieved_at: str) -> list[dict]:
    rows: list[dict] = []
    for index, function in enumerate(record.get("function") or []):
        if not isinstance(function, dict):
            continue
        def edam_term(key: str) -> list[str]:
            """Operation/term entries carry ``uri`` directly."""
            return [str(item["uri"]) for item in function.get(key) or []
                    if isinstance(item, dict) and item.get("uri")]

        def edam_data(key: str) -> list[str]:
            """Input/output entries nest the data type under ``data.uri``."""
            uris: list[str] = []
            for item in function.get(key) or []:
                if not isinstance(item, dict):
                    continue
                data = item.get("data")
                if isinstance(data, dict) and data.get("uri"):
                    uris.append(str(data["uri"]))
            return uris

        def edam_formats(key: str) -> list[str]:
            """Input/output entries carry a ``format`` list of ``uri`` objects."""
            uris: list[str] = []
            for item in function.get(key) or []:
                if not isinstance(item, dict):
                    continue
                for fmt in item.get("format") or []:
                    if isinstance(fmt, dict) and fmt.get("uri"):
                        uris.append(str(fmt["uri"]))
            return uris

        rows.append({
            "schema_version": 1,
            "biotools_id": accession,
            "function_key": f"{accession}:{index}:unbound:unbound",
            "function_name": function.get("name") or None,
            "edam_operations": edam_term("operation"),
            "edam_input_data": edam_data("input"),
            "edam_input_formats": edam_formats("input"),
            "edam_output_data": edam_data("output"),
            "edam_output_formats": edam_formats("output"),
            "interface": None,
            "upstream_version": None,
            "descriptor": {
                "url": None, "revision_or_digest": None,
                "identity_link_evidence_url": None, "supported_profile": None,
                "unsupported_semantics": [],
            },
            "proposed_node_id": None,
            "verification": {
                "focused_test_command": None, "focused_test_result": "not_run",
                "queued_run_id": None, "run_receipt_path": None,
                "oracle_result": "not_run",
            },
            "citations": [],
            "decision": "candidate",
            "blocker_code": None,
            "blocker_detail": None,
            "reviewed_by": None,
            "reviewed_at": None,
        })
    return rows


def priority_score(record: dict, types: set[str], labels: set[str], annotated: dict) -> tuple[int, list[str]]:
    """Transparent, documented selection score for the candidate cohort.

    Signals only. A high score selects a record for *attempted* admission; it is
    not evidence that the tool installs or that any run is scientifically valid.

    Signals are graded rather than purely boolean because a boolean sum saturates
    and leaves hundreds of records tied, which would make the "prioritization" an
    alphabetical accident rather than a choice. Publication count is a coarse
    research-use proxy and is capped deliberately; it is not a quality, recency,
    or citation-correctness judgement.
    """
    score = 0
    reasons: list[str] = []
    if "Command-line tool" in types:
        score += 3
        reasons.append("+3 command-line tool")
    if types & DESCRIPTOR_TYPES:
        score += 3
        reasons.append("+3 machine-readable descriptor")
    if types & CWL_DESCRIPTOR_TYPES:
        score += 2
        reasons.append("+2 CWL descriptor specifically")
    if types & CONTAINER_TYPES:
        score += 2
        reasons.append("+2 container image")
    if types & PACKAGE_TYPES:
        score += 2
        reasons.append("+2 package/binary distribution")
    if "command-line specification" in types:
        score += 1
        reasons.append("+1 explicit command-line specification")
    if annotated["edam_operation"]:
        score += 2
        reasons.append("+2 EDAM operation annotated")
    if annotated["input_format"]:
        score += 1
        reasons.append("+1 input format annotated")
    if annotated["output_format"]:
        score += 1
        reasons.append("+1 output format annotated")
    if annotated["documentation"]:
        score += 1
        reasons.append("+1 documentation URL")
    if annotated["license"]:
        score += 1
        reasons.append("+1 license declared")
    publications = len(record.get("publication") or [])
    if publications:
        bonus = min(publications, 5)
        score += bonus
        reasons.append(f"+{bonus} publication proxy for research use (capped at 5)")
    topics = len(record.get("topic") or [])
    if topics:
        bonus = min(topics, 2)
        score += bonus
        reasons.append(f"+{bonus} EDAM topic annotation")
    operations = sum(len(f.get("operation") or []) for f in record.get("function") or []
                     if isinstance(f, dict))
    if operations:
        bonus = min(operations, 3)
        score += bonus
        reasons.append(f"+{bonus} EDAM operation count")
    if "Linux" in (record.get("operatingSystem") or []):
        score += 1
        reasons.append("+1 declares Linux support")
    if annotated["version"]:
        score += 1
        reasons.append("+1 version label present")
    return score, reasons


def declared_links(root: Path) -> dict[str, str]:
    """node_id -> accession, from checked-in generated links plus typed specs."""
    declared: dict[str, str] = {}
    links_path = root / "bionodulo/nodes/generated/biotools_links.json"
    if links_path.is_file():
        for node, entry in read_json(links_path).get("links", {}).items():
            if entry.get("found") and entry.get("biotoolsID"):
                declared[node] = str(entry["biotoolsID"]).lower()
    try:
        from scripts.link_biotools import EXPLICIT_IDS
    except Exception:
        EXPLICIT_IDS = {}
    for node, accession in EXPLICIT_IDS.items():
        declared[node] = str(accession).lower()
    ui_path = root / "bionodulo/nodes/generated/catalog.ui.json"
    if ui_path.is_file():
        for node in read_json(ui_path).get("nodes", {}).values():
            tool_id = (node.get("identity") or {}).get("tool_id")
            machine_id = (node.get("identity") or {}).get("machine_id")
            if tool_id and machine_id:
                declared[machine_id] = str(tool_id).lower()
    return declared


def build(snapshot_dir: Path, output_dir: Path, cohort_size: int, root: Path = ROOT,
          outcomes_path: Path | None = None) -> dict:
    manifest = read_json(snapshot_dir / "manifest.json")
    if not manifest.get("complete"):
        raise ValueError("A complete, verified registry snapshot is required")
    outcomes = read_json(outcomes_path) if outcomes_path and outcomes_path.is_file() else {}
    curated = {key.lower(): value for key, value in (outcomes.get("records") or {}).items()}
    cohort_default = outcomes.get("cohort_default_outcome") or {}
    registry_path = snapshot_dir / "registry.jsonl"
    digest = hashlib.sha256()
    with registry_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError("Registry snapshot hash does not match its manifest")

    node_index = read_json(root / "bionodulo/nodes/node_index.json")
    metadata = read_json(root / "bionodulo/nodes/node_metadata.json")
    declared = declared_links(root)
    by_accession: dict[str, list[str]] = defaultdict(list)
    for node, accession in declared.items():
        if node in node_index:
            by_accession[accession].append(node)

    output_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = manifest["completed_at"]
    reported_count = manifest["records"]

    parent_rows: list[dict] = []
    function_out: list[dict] = []
    cohort: list[dict] = []
    state_counts: Counter = Counter()
    blocker_counts: Counter = Counter()
    interface_counts: Counter = Counter()
    type_counts: Counter = Counter()
    reconciliation_counts: Counter = Counter()
    annotation_counts: Counter = Counter()
    seen: set[str] = set()
    duplicates: list[str] = []

    with registry_path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            accession = record["biotoolsID"]
            key = accession.lower()
            if key in seen:
                duplicates.append(accession)
                continue
            seen.add(key)

            raw = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            types_list = [str(t) for t in (record.get("toolType") or []) if t]
            types = set(types_list)
            labels = link_types(record)
            declared_types, invocable, annotated_interface = classify_interfaces(types_list)
            functions = record.get("function") or []
            annotations = {
                "edam_operation": any(f.get("operation") for f in functions if isinstance(f, dict)),
                "edam_topic": bool(record.get("topic")),
                "input_format": any(i.get("format") for f in functions if isinstance(f, dict)
                                    for i in f.get("input") or [] if isinstance(i, dict)),
                "output_format": any(i.get("format") for f in functions if isinstance(f, dict)
                                     for i in f.get("output") or [] if isinstance(i, dict)),
                "documentation": bool(record.get("documentation")),
                "version": bool(record.get("version")),
                "license": bool(record.get("license")),
                "homepage": bool(record.get("homepage")),
            }
            annotation_counts.update({k: int(v) for k, v in annotations.items()})
            type_counts.update(types_list or ["Unspecified"])
            if not types_list:
                interface_counts["unannotated"] += 1
            elif invocable:
                interface_counts["machine_invocable"] += 1
            else:
                interface_counts["non_executable_only"] += 1

            existing_nodes = sorted(by_accession.get(key, []))
            descriptor_hits = sorted(labels & DESCRIPTOR_TYPES)
            container_hits = sorted(labels & CONTAINER_TYPES)
            package_hits = sorted(labels & PACKAGE_TYPES)
            score, reasons = priority_score(record, types, labels, annotations)

            # ---- reconciliation -------------------------------------------
            if existing_nodes:
                reconciliation = "existing_exact"
                family = None
                if existing_nodes:
                    module = node_index.get(existing_nodes[0], "")
                    family = module.split("builtin.")[-1].split(".")[0].removesuffix("_family") or None
                evidence = [
                    f"declared link: {node} -> https://bio.tools/{accession}"
                    for node in existing_nodes
                ]
            elif not types_list:
                reconciliation = "unreviewed"
                family = None
                evidence = []
            else:
                reconciliation = "no_existing_node"
                family = None
                evidence = []
            reconciliation_counts[reconciliation] += 1

            # A name-based family match is a search hint, never identity. The
            # playbook is explicit that display-name similarity must not be used
            # to infer record identity, so this only shapes cohort ordering.
            normalized = re.sub(r"[^a-z0-9]", "", accession.casefold())
            family_hints = sorted({
                module.split("builtin.")[-1].split(".")[0].removesuffix("_family")
                for node, module in node_index.items()
                if len(normalized) >= 4
                and re.sub(r"[^a-z0-9]", "", node.casefold()).startswith(normalized)
            })

            # ---- terminal state -------------------------------------------
            blockers: list[dict] = []
            if reconciliation == "existing_exact":
                state = "reference_only"
                next_action = (
                    "Covered by an existing builtin. That builtin is evidence_pending in the "
                    "operational catalog, so no executable admission is claimed here."
                )
            elif not types_list:
                state = "reference_only"
                next_action = (
                    "Interface unannotated in bio.tools. Inspect homepage/repository for a machine "
                    "interface before selecting; missing annotation is not evidence of no capability."
                )
            elif not invocable:
                state = "blocked"
                blockers.append({
                    "code": "no_machine_invocation",
                    "detail": "Declared tool types have no local machine invocation: "
                              + ", ".join(sorted(types)),
                })
                next_action = (
                    "Keep visible as reference metadata. Revisit only if the record later declares "
                    "a command-line, library, or descriptor interface."
                )
            else:
                state = "reference_only"
                next_action = (
                    "Machine-invocable and in the unprocessed tail. Selected for a later cohort once "
                    "the current batch's admission rate is measured."
                )

            row = {
                "schema_version": 1,
                "biotools_id": accession,
                "record_url": f"https://bio.tools/{accession}",
                "snapshot": {
                    "retrieved_at_utc": retrieved_at,
                    "source_page_url": manifest["source"],
                    "raw_sha256": sha256_text(raw),
                    "reported_count": reported_count,
                },
                "registry_identity": {
                    "name": record.get("name") or None,
                    "tool_types": types_list,
                    "homepage": record.get("homepage") or None,
                    "version_labels": [str(v) for v in record.get("version") or []],
                    "functions": [
                        {
                            "index": index,
                            "name": f.get("name") or None,
                            "operations": [i.get("uri") for i in f.get("operation") or []
                                           if isinstance(i, dict)],
                        }
                        for index, f in enumerate(functions) if isinstance(f, dict)
                    ],
                    "publication_identifiers": [
                        {"doi": p.get("doi"), "pmid": p.get("pmid"), "pmcid": p.get("pmcid"),
                         "type": (p.get("type") or {}).get("term") if isinstance(p.get("type"), dict) else None}
                        for p in record.get("publication") or [] if isinstance(p, dict)
                    ],
                    "download_urls": [
                        {"type": d.get("type"), "url": d.get("url")}
                        for d in (record.get("download") or []) if isinstance(d, dict) and d.get("url")
                    ],
                },
                "reconciliation": {
                    "status": reconciliation,
                    "existing_node_ids": existing_nodes,
                    "family": family,
                    "identity_evidence": evidence,
                    "aliases_or_duplicates": [],
                    "family_hint": family_hints or None,
                    "reviewer": None,
                },
                "candidate_operations": [],
                "state": state,
                "blockers": blockers,
                "next_action": next_action,
                "owner": None,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                "evidence": {
                    "interface_classes": declared_types,
                    "machine_invocable": invocable,
                    "interface_annotated": annotated_interface,
                    "descriptor_candidates": descriptor_hits,
                    "container_candidates": container_hits,
                    "package_candidates": package_hits,
                    "annotations": annotations,
                    "priority_score": score,
                    "priority_reasons": reasons,
                    "license": record.get("license") or None,
                    "operating_systems": [str(o) for o in record.get("operatingSystem") or []],
                    "languages": [str(x) for x in record.get("language") or []],
                    "accessibility": record.get("accessibility") or None,
                    "admission_note": "metadata_only; not installed, not executed, not scientifically validated",
                },
            }
            parent_rows.append(row)
            function_out.extend(function_rows(record, accession, retrieved_at))
            if invocable and not existing_nodes:
                cohort.append({
                    "biotools_id": accession,
                    "name": row["registry_identity"]["name"],
                    "types": types_list,
                    "score": score,
                    "reasons": reasons,
                    "descriptor_candidates": descriptor_hits,
                    "container_candidates": container_hits,
                    "package_candidates": package_hits,
                    "has_edam_operation": annotations["edam_operation"],
                    "publications": len(record.get("publication") or []),
                    "state": "reference_only",
                })
            state_counts[state] += 1
            for blocker in blockers:
                blocker_counts[blocker["code"]] += 1

    # ---- cohort selection -------------------------------------------------
    cohort.sort(key=lambda item: (-item["score"], item["biotools_id"].casefold()))
    selected = cohort[:cohort_size]
    selected_ids = {item["biotools_id"].lower() for item in selected}
    for row in parent_rows:
        if row["biotools_id"].lower() in selected_ids:
            row["state"] = "candidate"
            row["owner"] = "unassigned-cohort"
            row["next_action"] = (
                "Assemble a source dossier: official invocation documentation, exact source "
                "release/commit or wrapper digest, expected arguments, inputs/outputs, error modes, "
                "license/access terms, package or container identity, reference-data dependency, "
                "and a real fixture. Then attempt install, focused test, queued run, and an "
                "independent oracle."
            )
            row["reconciliation"]["status"] = (
                row["reconciliation"]["status"]
                if row["reconciliation"]["status"] != "no_existing_node"
                else "new_operation"
            )

    # Curated outcomes override the mechanical defaults. They record what was
    # actually attempted and measured, not what the metadata implies. A selected
    # cohort record with no explicit outcome receives the cohort default, which
    # in this assignment is the measured host platform blocker.
    for row in parent_rows:
        key = row["biotools_id"].lower()
        override = curated.get(key)
        if override is None and key in selected_ids and cohort_default:
            override = cohort_default
            row["evidence"]["cohort_selected"] = True
        if override is None:
            continue
        if override.get("state"):
            row["state"] = override["state"]
        if override.get("reconciliation_status"):
            row["reconciliation"]["status"] = override["reconciliation_status"]
        if "owner" in override:
            row["owner"] = override["owner"]
        if override.get("next_action"):
            row["next_action"] = override["next_action"]
        if override.get("blocker_code"):
            row["blockers"] = [{"code": override["blocker_code"],
                                "detail": override.get("blocker_detail", "")}]
        elif override.get("state") and override["state"] != "blocked":
            # A record that is no longer blocked must not keep a stale blocker, or
            # the blocker histogram would count it while the state table would not.
            row["blockers"] = []
        for field in ("verified_operations", "operation_provenance", "evidence", "note"):
            if override.get(field) is not None:
                row["evidence"][field] = override[field]
        if override.get("note"):
            row["evidence"]["admission_note"] = override["note"]
    verified_ids = sorted(row["biotools_id"] for row in parent_rows
                          if row["state"] == "executable_admitted")
    state_counts = Counter(row["state"] for row in parent_rows)
    blocker_counts = Counter(blocker["code"] for row in parent_rows for blocker in row["blockers"])
    reconciliation_counts = Counter(row["reconciliation"]["status"] for row in parent_rows)

    ledger_path = output_dir / "ledger.jsonl"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in parent_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    functions_path = output_dir / "ledger-functions.jsonl"
    with functions_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in function_out:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    cohort_path = output_dir / "expansion-cohort.jsonl"
    with cohort_path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in selected:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")

    coverage = {
        "snapshot_sha256": manifest["sha256"],
        "snapshot_records": manifest["records"],
        "snapshot_started_at": manifest["started_at"],
        "snapshot_completed_at": manifest["completed_at"],
        "ledger_parent_rows": len(parent_rows),
        "ledger_function_rows": len(function_out),
        "unique_accessions": len(seen),
        "duplicate_accessions": duplicates,
        "coverage_complete": len(parent_rows) == manifest["records"],
        "states": dict(state_counts),
        "blocker_codes": dict(blocker_counts),
        "interface_classes": dict(interface_counts),
        "registry_tool_types_nonexclusive": dict(type_counts.most_common()),
        "annotation_coverage": dict(annotation_counts),
        "reconciliation": dict(reconciliation_counts),
        "indexed_builtins": len(node_index),
        "visible_node_metadata": len(metadata),
        "declared_link_nodes": len(by_accession),
        "cohort": {
            "method": (
                "Deterministic score over metadata signals: command-line type, machine-readable "
                "descriptor, container, package distribution, EDAM operation annotation, "
                "documentation URL, license, publication count as a research-use proxy, declared "
                "Linux support, version label. Selection targets attempted admission only."
            ),
            "size": len(selected),
            "pool_machine_invocable_without_existing_node": len(cohort),
            "score_range": [selected[-1]["score"], selected[0]["score"]] if selected else None,
            "score_histogram_pool": dict(sorted(Counter(item["score"] for item in cohort).items())),
            "tie_at_cutoff": sum(1 for item in cohort if selected and item["score"] == selected[-1]["score"]),
            "selected": [item["biotools_id"] for item in selected],
        },
        "executable_admitted_records": verified_ids,
        "executable_admitted_count": len(verified_ids),
        "host_constraint": outcomes.get("host_constraint"),
        "curated_outcomes_applied": sorted(curated),
        "not_established": [
            "registry_entries_installed", "registry_entries_executed",
            "registry_entries_scientifically_validated",
        ],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output_dir / "ledger-summary.json").write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(coverage, indent=2, ensure_ascii=False))
    return coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cohort-size", type=int, default=40)
    parser.add_argument("--outcomes", type=Path, default=None,
                        help="Curated outcome file layered over the mechanical default states.")
    args = parser.parse_args()
    build(args.snapshot_dir, args.output_dir, args.cohort_size, outcomes_path=args.outcomes)


if __name__ == "__main__":
    main()

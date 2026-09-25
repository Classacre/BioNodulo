#!/usr/bin/env python
"""Compare a complete bio.tools snapshot with every local node; export discovery.

Declared links and exact-name candidates are deliberately separate. Neither
means a binary is installed or an analysis has been scientifically validated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.link_biotools import EXPLICIT_IDS, summarize  # noqa: E402


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def declared_links(root: Path) -> dict[str, str]:
    links = read_json(root / "bionodulo/nodes/generated/biotools_links.json")["links"]
    declared = {node: entry["biotoolsID"].lower() for node, entry in links.items()
                if entry.get("found") and entry.get("biotoolsID")}
    declared.update({node: accession.lower() for node, accession in EXPLICIT_IDS.items()})
    typed = read_json(root / "bionodulo/nodes/generated/catalog.ui.json")["nodes"]
    for node in typed.values():
        identity = node["identity"]
        if identity.get("tool_id"):
            declared[identity["machine_id"]] = identity["tool_id"].lower()
    return declared


def audit(snapshot_dir: Path, output_dir: Path, *, root: Path = ROOT, check_imports: bool = False) -> dict:
    manifest = read_json(snapshot_dir / "manifest.json")
    if not manifest.get("complete"):
        raise ValueError("A complete, verified registry snapshot is required")
    if sha256(snapshot_dir / "registry.jsonl") != manifest["sha256"]:
        raise ValueError("Registry snapshot hash does not match its manifest")
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = root / "bionodulo/nodes/node_index.json"
    metadata_path = root / "bionodulo/nodes/node_metadata.json"
    metadata = read_json(metadata_path)
    node_index = read_json(index_path)
    operational = read_json(root / "bionodulo/nodes/generated/catalog.operational.json")
    declared = declared_links(root)
    candidate_terms = defaultdict(set)
    declared_by_tool = defaultdict(list)
    for node, accession in declared.items():
        if node in node_index:
            declared_by_tool[accession].append(node)
    inventory = []
    for node, module in sorted(node_index.items()):
        meta = metadata.get(node, {})
        family = module.split("builtin.")[-1].split(".")[0].removesuffix("_family")
        terms = {node.lower(), family.lower()}
        terms.update(str(term).lower() for term in meta.get("required_executables", []))
        terms.update(str(term).lower().split("=")[0] for term in meta.get("required_conda_packages", []))
        for term in terms:
            candidate_terms[term].add(node)
        commands = meta.get("required_executables", [])
        available = {name: bool(shutil.which(name)) for name in commands}
        inventory.append({
            "node_id": node, "module": module, "family": family,
            "metadata_present": node in metadata, "declared_biotools_id": declared.get(node),
            "visual_only": bool(meta.get("visual_only")),
            "requires_external_tools": bool(meta.get("requires_external_tools")),
            "required_executables": commands, "executables_on_audit_host_PATH": available,
            "verification_status": operational["nodes"].get(node, {}).get("verification_status", "unknown"),
            "scientific_validation": "not_established_by_catalog_audit",
        })
    importability = None
    if check_imports:
        from bionodulo.nodes.registry import NodeRegistry
        registry = NodeRegistry.create_isolated()
        started = time.monotonic()
        rows = []
        for node_id in sorted(node_index):
            try:
                cls = registry.get(node_id)
                rows.append({"node_id": node_id, "imported": cls is not None,
                             "class": f"{cls.__module__}.{cls.__name__}" if cls else None,
                             "execution_tested": False})
            except Exception as exc:
                rows.append({"node_id": node_id, "imported": False, "error": str(exc), "execution_tested": False})
        importability = {"indexed": len(node_index), "imported": sum(row["imported"] for row in rows),
                         "failed": sum(not row["imported"] for row in rows),
                         "elapsed_seconds": round(time.monotonic() - started, 2),
                         "scope": "Importability only; no tool binary or node run method executed"}
        (output_dir / "node-importability.json").write_text(json.dumps({**importability, "rows": rows}, indent=2) + "\n", encoding="utf-8")
    counters = Counter()
    types = Counter()
    names = defaultdict(list)
    registry_ids = set()
    linked_nodes = set()
    candidate_nodes = set()
    refreshed_links = {}
    discovery_path = output_dir / "biotools-discovery.json"
    ledger_path = output_dir / "biotools-gap-ledger.jsonl"
    with (snapshot_dir / "registry.jsonl").open(encoding="utf-8") as source, \
            ledger_path.open("w", encoding="utf-8", newline="\n") as ledger, \
            discovery_path.open("w", encoding="utf-8", newline="\n") as discovery:
        header = {"schema_version": "1.0", "records": manifest["records"],
                  "snapshot_sha256": manifest["sha256"], "updated_at": manifest["completed_at"],
                  "source": manifest["source"], "license": manifest["license"]}
        discovery.write(json.dumps(header, separators=(",", ":"))[:-1] + ',"tools":[')
        for line in source:
            record = json.loads(line)
            accession = record["biotoolsID"]
            key = accession.lower()
            if key in registry_ids:
                raise ValueError(f"Duplicate registry accession: {accession}")
            registry_ids.add(key)
            name = record.get("name") or accession
            names[name.casefold()].append(accession)
            node_ids = sorted(declared_by_tool.get(key, []))
            candidates = sorted(candidate_terms.get(key, set()) - set(node_ids))
            linked_nodes.update(node_ids)
            candidate_nodes.update(candidates)
            for node in node_ids:
                refreshed_links[node] = {"biotools_id": accession, "queried": True,
                                         "found": True, **summarize(record)}
            functions = record.get("function") or []
            annotated = {"edam_operation": any(f.get("operation") for f in functions),
                         "input_format": any(i.get("format") for f in functions for i in f.get("input") or []),
                         "output_format": any(i.get("format") for f in functions for i in f.get("output") or []),
                         "documentation": bool(record.get("documentation")),
                         "version": bool(record.get("version"))}
            counters.update({key: int(value) for key, value in annotated.items()})
            counters["with_declared_node_links"] += bool(node_ids)
            counters["with_candidate_node_links"] += bool(candidates)
            counters["metadata_only_no_declared_node"] += not bool(node_ids)
            types.update(record.get("toolType") or ["Unspecified"])
            item = {"biotools_id": accession, "name": name, "declared_node_ids": node_ids,
                    "candidate_node_ids_requires_review": candidates, "metadata": annotated,
                    "catalog_status": "declared_node_link" if node_ids else "metadata_only",
                    "installation_status": "not_tested_for_registry_entry",
                    "execution_status": "not_tested_for_registry_entry",
                    "scientific_validation": "not_tested_for_registry_entry"}
            ledger.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            summary = {"id": accession, "name": name,
                       "description": re.sub(r"\s+", " ", record.get("description") or "").strip()[:360],
                       "types": record.get("toolType") or [], "nodes": node_ids,
                       "topics": [term.get("term", "") for term in record.get("topic") or []]}
            if len(registry_ids) > 1:
                discovery.write(",")
            discovery.write(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
        discovery.write("]}\n")
    if len(registry_ids) != manifest["records"]:
        raise ValueError("Ledger does not cover the complete snapshot")
    unresolved = {node: accession for node, accession in declared.items()
                  if node in node_index and accession not in registry_ids}
    aliases = defaultdict(list)
    for node in node_index:
        aliases[re.sub(r"[^a-z0-9]", "", node.casefold())].append(node)
    summary = {
        "schema_version": "1.0", "registry_manifest": manifest,
        "registry_records_compared": len(registry_ids), "ledger_rows": len(registry_ids),
        "indexed_nodes": len(node_index), "visible_node_metadata": len(metadata),
        "index_without_metadata": sorted(set(node_index) - set(metadata)),
        "metadata_without_index": sorted(set(metadata) - set(node_index)),
        "declared_linked_nodes": len(linked_nodes), "declared_linked_node_ids": sorted(linked_nodes),
        "nodes_without_declared_registry_link": sorted(set(node_index) - linked_nodes),
        "candidate_linked_nodes_needing_review": len(candidate_nodes - linked_nodes),
        "unresolved_declared_links": unresolved, "counts": dict(counters),
        "registry_tool_types_nonexclusive": dict(types.most_common()),
        "duplicate_registry_names_distinct_accessions": {n: ids for n, ids in names.items() if len(ids) > 1},
        "normalized_node_id_collision_candidates": {n: ids for n, ids in aliases.items() if len(ids) > 1},
        "operational_catalog_summary": operational.get("summary"),
        "importability_verified_this_audit": importability,
        "host_PATH_node_dependency_checks": {
            "nodes_declaring_executables": sum(bool(row["required_executables"]) for row in inventory),
            "nodes_with_all_declared_executables_on_PATH": sum(bool(row["required_executables"]) and all(row["executables_on_audit_host_PATH"].values()) for row in inventory),
            "scope": "Audit host PATH only; excludes WSL/Conda/container/cloud environments and does not establish execution success",
        },
        "registry_entries_execution_validated_this_catalog_audit": 0,
        "registry_entries_scientifically_validated_this_catalog_audit": 0,
        "evidence_files": {"node_index_sha256": sha256(index_path), "node_metadata_sha256": sha256(metadata_path),
                           "ledger_sha256": sha256(ledger_path), "discovery_sha256": sha256(discovery_path)},
    }
    for filename, value in [("biotools-coverage.json", summary), ("node-inventory.json", inventory),
                            ("biotools-links-refreshed.json", {"schema_version": "0.1", "source": manifest["source"],
                            "snapshot_sha256": manifest["sha256"], "found": len(refreshed_links),
                            "linked_node_types": len(refreshed_links), "links": refreshed_links})]:
        (output_dir / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"registry_records": len(registry_ids), "indexed_nodes": len(node_index),
                      "declared_linked_nodes": len(linked_nodes), "counts": dict(counters)}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--check-imports", action="store_true", help="Import every indexed class without executing its tool")
    args = parser.parse_args()
    audit(args.snapshot_dir, args.output_dir, check_imports=args.check_imports)


if __name__ == "__main__":
    main()

"""Exhaustively prove source-to-node coverage without claiming executable coverage."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from contextlib import closing
from pathlib import Path
from time import perf_counter

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.generation.discovery import _verified_records
from bionodulo.nodes.registry import NodeRegistry, _to_node_info
from bionodulo.nodes.registry_catalog import (
    DEFAULT_CATALOG,
    RegistryCatalog,
    RegistryCatalogError,
    RegistryExecutionUnavailable,
    bind_registry_definition,
    generated_node_id,
    registry_execution_blockers,
)


async def verify(catalog: Path, snapshot: Path, manifest_path: Path) -> dict:
    started = perf_counter()
    reader = RegistryCatalog(catalog)
    metadata = reader.verify()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if metadata["sha256"] != manifest["sha256"]:
        raise RegistryCatalogError("Catalog and source snapshot digests differ")
    os.environ["BIONODULO_REGISTRY_CATALOG"] = str(catalog)
    seen = set()
    source_verified = 0
    refused = 0
    # One class at a time in this isolated verification process. The app lazily
    # creates only requested classes; don't retain 34k temporary verification classes.
    with closing(reader._connect()) as db:
        for record in _verified_records(snapshot, manifest):
            node_id = generated_node_id(record["biotoolsID"])
            row = db.execute("SELECT definition FROM definitions WHERE node_id=?", (node_id,)).fetchone()
            if row is None:
                raise RegistryCatalogError("A source record has no generated definition")
            definition = reader._decode(row[0])
            if definition["source_record"] != record or node_id in seen:
                raise RegistryCatalogError("Source record mismatch or duplicate generated node")
            seen.add(node_id)
            source_verified += 1
            node_class = bind_registry_definition(definition)
            try:
                info = _to_node_info(node_class)
                workflow = {"nodes": [{"id": "generated", "type": node_id, "node_info": info}], "edges": []}
                if json.loads(json.dumps(workflow)) != workflow:
                    raise RegistryCatalogError("Node metadata does not round-trip through workflow JSON")
                if not registry_execution_blockers(workflow, None):
                    raise RegistryCatalogError("Definition-only node passed execution admission")
                try:
                    await node_class().run()
                except RegistryExecutionUnavailable:
                    refused += 1
                else:
                    raise RegistryCatalogError("Definition-only node executed")
            finally:
                BaseNode._SUBCLASSES.remove(node_class)
    if source_verified != manifest["records"] or refused != source_verified:
        raise RegistryCatalogError("Coverage denominator mismatch")
    registry = NodeRegistry.create_isolated()
    # Deterministic sampling exercises the actual lazy lookup in addition to the
    # exhaustive metadata/serialization/refusal adapter checks above.
    lazy_ids = sorted(seen)[::1000]
    for node_id in lazy_ids:
        if registry.object_info(node_id)["registry_origin"]["execution_status"] != "definition_only":
            raise RegistryCatalogError("Lazy registry metadata mismatch")
    return {
        **metadata, "source_records_verified": source_verified, "source_accessions_missing": 0,
        "source_accessions_duplicated": 0, "metadata_round_trips": source_verified,
        "direct_execution_refusals": refused, "lazy_lookup_samples": len(lazy_ids),
        "catalog_file_sha256": hashlib.sha256(catalog.read_bytes()).hexdigest(),
        "catalog_bytes": catalog.stat().st_size, "elapsed_seconds": round(perf_counter() - started, 3),
        "claim": "100% definition generation for this snapshot; no new executable or biological validation claim.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(verify(args.catalog, args.snapshot, args.manifest))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(json.dumps(report, indent=2, ensure_ascii=False).encode() + b"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

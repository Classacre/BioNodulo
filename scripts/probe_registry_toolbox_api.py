"""Enumerate every generated definition through a local running app API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from bionodulo.nodes.registry_catalog import generated_node_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8187")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This no-execution acceptance probe targets a local test app only")
    started = perf_counter()
    seen: set[str] = set()
    samples = []
    offset = 0
    pages = 0
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        first = client.get("/api/registry/nodes", params={"limit": 100}).raise_for_status().json()
        total, snapshot = first["total"], first["snapshot"]["sha256"]
        while offset < total:
            page = first if offset == 0 else client.get("/api/registry/nodes", params={
                "offset": offset, "limit": 100,
            }).raise_for_status().json()
            assert page["total"] == page["matched_count"] == total
            assert page["snapshot"]["sha256"] == snapshot
            assert len(page["entries"]) == min(100, total - offset)
            for entry in page["entries"]:
                node_id = entry["node_id"]
                assert node_id == generated_node_id(entry["accession"]) and node_id not in seen
                assert entry["execution_status"] == "definition_only" and not entry["runnable_node_ids"]
                if len(seen) % 1000 == 0:
                    info = client.get(f"/api/object_info/{node_id}").raise_for_status().json()
                    assert info["registry_origin"]["source_snapshot_sha256"] == snapshot
                    workflow = {"nodes": [{"id": "probe", "type": node_id, "node_info": info}], "edges": []}
                    readiness = client.post("/api/workflow/validate", json={"workflow": workflow})
                    assert readiness.raise_for_status().json()["environment"]["execution_ready"] is False
                    refused = client.post("/api/runs", json={"workflow": workflow})
                    assert refused.status_code == 400 and refused.json()["detail"]["blockers"]
                    samples.append({"accession": entry["accession"], "node_id": node_id,
                                    "metadata_status": 200, "execution_ready": False, "run_admission_status": 400})
                seen.add(node_id)
            offset += 100
            pages += 1
        assert len(seen) == total
        assert client.get("/api/registry/nodes", params={"offset": total}).json()["entries"] == []
    report = {"schema_version": 1, "snapshot_sha256": snapshot, "api_records": len(seen),
              "api_pages": pages, "duplicate_ids": 0, "samples": samples,
              "elapsed_seconds": round(perf_counter() - started, 3),
              "scope": "Every catalog entry exposed by API; deterministic metadata/readiness/refusal samples, no tool execution."}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(json.dumps(report, indent=2).encode() + b"\n")
    print(json.dumps({key: value for key, value in report.items() if key != "samples"}, indent=2))


if __name__ == "__main__":
    main()

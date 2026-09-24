"""Whole-source generation, app persistence and non-execution admission contracts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bionodulo.nodes.registry import NodeRegistry
from bionodulo.nodes.registry_catalog import (
    EXECUTION_BLOCKER,
    RegistryCatalog,
    RegistryCatalogError,
    RegistryExecutionUnavailable,
    generate_catalog,
    generated_node_id,
    registry_execution_blockers,
)


def _snapshot(tmp_path: Path, records: list[dict]) -> tuple[Path, Path]:
    content = b"".join(json.dumps(item, ensure_ascii=False).encode() + b"\n" for item in records)
    source = tmp_path / "source.jsonl"
    source.write_bytes(content)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "records": len(records), "sha256": hashlib.sha256(content).hexdigest(), "complete": True,
        "completed_at": "2026-09-24T00:00:00Z", "source": "https://bio.tools/api/tool/",
    }))
    return source, manifest


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    # Synthetic schema fixtures test the generator; production acceptance uses every real source record.
    records = [
        {"biotoolsID": "NoExecutable", "name": "No executable", "description": "A database portal",
         "toolType": ["Database portal"], "topic": [{"term": "Genomics"}],
         "function": [{"operation": [{"term": "Sequence analysis"}]}]},
        {"biotoolsID": "unicode", "name": "Str\u00e4\u00df\u00eb_100%", "description": "A literal wildcard"},
        {"biotoolsID": "third", "name": "Third", "description": "Another record"},
    ]
    source, manifest = _snapshot(tmp_path, records)
    path = tmp_path / "catalog.sqlite"
    generate_catalog(source, manifest, path)
    monkeypatch.setenv("BIONODULO_REGISTRY_CATALOG", str(path))
    return RegistryCatalog(path), records, source, manifest


def test_every_record_generates_one_stable_definition_without_executable_claim(catalog):
    reader, records, _, _ = catalog
    report = reader.verify()
    assert report["records"] == report["verified_definitions"] == len(records)
    assert report["executable_definitions"] == 0
    registry = NodeRegistry.create_isolated()
    for record in records:
        node_id = generated_node_id(record["biotoolsID"])
        assert node_id == generated_node_id(record["biotoolsID"].upper())
        assert reader.get(node_id)["source_record"] == record
        info = registry.object_info(node_id)
        assert info["registry_origin"]["execution_status"] == "definition_only"
        assert info["registry_origin"]["blockers"] == [EXECUTION_BLOCKER]
        assert info["input"] == {"required": {}, "optional": {}, "hidden": {}}
        assert info["output"] == [] and info["visual_only"] is False
        with pytest.raises(RegistryExecutionUnavailable):
            asyncio.run(registry.get(node_id)().run())


def test_custom_registration_cannot_shadow_a_generated_definition(catalog):
    from bionodulo.nodes.registry_catalog import bind_registry_definition

    reader, records, _, _ = catalog
    node_id = generated_node_id(records[0]["biotoolsID"])
    registry = NodeRegistry.create_isolated()
    # Even a class carrying apparently legitimate origin metadata cannot claim an ID.
    custom_class = bind_registry_definition(reader.get(node_id))
    for loaded in (False, True):
        if loaded:
            registry.get(node_id)
        with pytest.raises(ValueError, match="namespace is reserved"):
            registry.register(custom_class, custom_node_source="custom-package")
    assert registry.object_info(node_id)["registry_origin"]["accession"] == records[0]["biotoolsID"]
    assert node_id not in registry._custom_node_sources


def test_search_pagination_unicode_and_literal_wildcards(catalog):
    reader, records, _, _ = catalog
    first = reader.search(limit=1)
    assert first["total"] == first["matched_count"] == len(records)
    assert first["entries"] != reader.search(limit=1, offset=1)["entries"]
    assert reader.search(offset=999)["entries"] == []
    for query in ("STR\u00c4SS\u00cb", "_", "%", "100%"):
        assert reader.search(query)["entries"][0]["accession"] == "unicode"
        assert reader.search(query)["matched_count"] == 1
    assert reader.search("Sequence analysis")["entries"][0]["accession"] == "NoExecutable"
    assert reader.search("' OR 1=1 --")["entries"] == []
    for kwargs in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"query": "x" * 257}):
        with pytest.raises(RegistryCatalogError):
            reader.search(**kwargs)


def test_search_ranks_exact_accession_and_name_before_partial_matches(tmp_path):
    records = [
        {"biotoolsID": "partial", "name": "A partial Needle match"},
        {"biotoolsID": "Needle", "name": "Z exact accession"},
        {"biotoolsID": "exact-name", "name": "Needle"},
    ]
    source, manifest = _snapshot(tmp_path, records)
    path = tmp_path / "ranking.sqlite"
    generate_catalog(source, manifest, path)
    result = RegistryCatalog(path).search("NEEDLE", limit=2)
    assert result["matched_count"] == 3
    assert {entry["accession"] for entry in result["entries"]} == {"Needle", "exact-name"}


def test_generation_atomic_on_bad_digest_duplicate_and_count(catalog, tmp_path):
    reader, records, source, manifest = catalog
    previous = reader.path.read_bytes()
    data = json.loads(manifest.read_text())
    data["sha256"] = "0" * 64
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        generate_catalog(source, manifest, reader.path)
    assert reader.path.read_bytes() == previous
    source, manifest = _snapshot(tmp_path, records + [{**records[0], "biotoolsID": "NOEXECUTABLE"}])
    with pytest.raises(ValueError):
        generate_catalog(source, manifest, reader.path)
    assert reader.path.read_bytes() == previous
    source, manifest = _snapshot(tmp_path, records)
    data = json.loads(manifest.read_text())
    data["records"] += 1
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        generate_catalog(source, manifest, reader.path)
    assert reader.path.read_bytes() == previous


def test_packed_catalog_reproducible_and_verified(catalog, tmp_path):
    reader, _, source, manifest = catalog
    first, second = tmp_path / "first.sqlite.gz", tmp_path / "second.sqlite.gz"
    generate_catalog(source, manifest, first)
    generate_catalog(source, manifest, second)
    assert first.read_bytes() == second.read_bytes()
    assert RegistryCatalog(first).verify() == reader.verify()


def test_catalog_corruption_and_forged_execution_refused(catalog):
    reader, records, _, _ = catalog
    node_id = generated_node_id(records[0]["biotoolsID"])
    value = reader.get(node_id)
    value["execution_status"] = "verified"
    with sqlite3.connect(reader.path) as db:
        db.execute("UPDATE definitions SET definition=? WHERE node_id=?",
                   (zlib.compress(json.dumps(value).encode()), node_id))
    with pytest.raises(RegistryCatalogError, match="authorize execution"):
        reader.get(node_id)


def test_server_admission_blocks_unknown_forged_and_nested_definitions(tmp_path):
    node_id = generated_node_id("not-in-current-snapshot")
    node = {"id": "a", "type": node_id, "node_info": {"registry_origin": {"execution_status": "verified"}}}
    workflows = [
        {"nodes": [node]}, {"nodes": {"a": node}},
        {"nodes": [{"id": "outer", "type": "subgraph", "params": {"workflow": {"nodes": [node]}}}]},
    ]
    registry = SimpleNamespace(get=lambda _: type("ForgedClass", (), {}))
    from bionodulo.execution.executor import WorkflowExecutor
    from bionodulo.manager.resolver import resolve_workflow

    for workflow in workflows:
        assert registry_execution_blockers(workflow, registry)
        report = resolve_workflow(workflow, registry, tmp_path)
        assert not report.execution_ready and not report.installable
        executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=registry)
        result = asyncio.run(executor.execute("never-run", workflow))
        assert result["status"] == "failed" and EXECUTION_BLOCKER in result["error"]
        preview = asyncio.run(executor.dry_run("never-run", workflow))
        assert preview["status"] == "failed"
    assert not (tmp_path / "runs" / "never-run").exists()


def test_real_api_search_lazy_metadata_reload_and_admission(catalog, monkeypatch):
    from bionodulo.api import routes

    reader, records, _, _ = catalog
    app = FastAPI()
    app.include_router(routes.router, prefix="/api")
    registry = NodeRegistry.create_isolated()
    app.state.node_registry = registry
    monkeypatch.setattr(routes, "_require_execute_permission", lambda *args: None)
    # Queue and settings are intentionally absent: refusal must happen before submission/provisioning.
    with TestClient(app) as client:
        response = client.get("/api/registry/nodes", params={"q": "NoExecutable", "limit": 1})
        assert response.status_code == 200
        entry = response.json()["entries"][0]
        node_id = entry["node_id"]
        assert entry["runnable_node_ids"] == []
        assert registry.all() == {}  # Searching never materializes thousands of node classes.
        info = client.get(f"/api/object_info/{node_id}").json()
        assert info["name"] == node_id
        saved = json.loads(json.dumps({"nodes": [{"id": "a", "type": node_id, "node_info": info}], "edges": []}))
        app.state.node_registry = NodeRegistry.create_isolated()
        assert client.get(f"/api/object_info/{node_id}").json() == info
        readiness = client.post("/api/workflow/validate", json={"workflow": saved})
        assert readiness.status_code == 200
        assert readiness.json()["environment"]["execution_ready"] is False
        response = client.post("/api/runs", json={"workflow": saved})
        assert response.status_code == 400 and response.json()["detail"]["blockers"]
        assert client.post("/api/hpc/submit", json={"workflow": saved, "name": "Blocked"}).status_code == 400
        assert client.get("/api/registry/nodes?limit=101").status_code == 422
        assert client.get("/api/registry/nodes?offset=-1").status_code == 422
        assert client.get("/api/object_info/biotools_" + "0" * 32).status_code == 404

"""Opt-in app queue proof for one source-derived, digest-locked OCI CWL node."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bionodulo.nodes.registry import NodeRegistry
from scripts.oci_twobit_oracle import decode_twobit


pytestmark = pytest.mark.skipif(
    not os.environ.get("BIONODULO_OCI_E2E_CATALOG"),
    reason="explicit OCI app catalog and audit runtime are required",
)


def test_oci_app_discovery_readiness_queue_publication_and_crate(tmp_path: Path, monkeypatch) -> None:
    catalog = Path(os.environ["BIONODULO_OCI_E2E_CATALOG"])
    catalog_bytes = catalog.read_bytes()
    catalog_specs = json.loads(catalog_bytes)["specs"]
    assert len(catalog_specs) == 16
    ucsc_specs = [
        spec for spec in catalog_specs
        if spec.get("cwl_oci", {}).get("source_uri", "").endswith(
            "/ucscuserapps/ucsc-fa-to-twobit.cwl"
        )
    ]
    assert len(ucsc_specs) == 1
    node_id = ucsc_specs[0]["identity"]["machine_id"]
    runtime = Path(os.environ["BIONODULO_OCI_E2E_RUNTIME"])
    fixture = Path(os.environ["BIONODULO_OCI_E2E_FIXTURE"])
    evidence = Path(os.environ["BIONODULO_OCI_E2E_EVIDENCE"])
    root = tmp_path / "app"
    root.mkdir()
    (root / "bionodulo.json").write_text(json.dumps({"execution": {
        "env_isolation": "auto", "max_workers": 1, "content_hashing": "strong",
    }}), encoding="utf-8")
    for key, value in {
        "BIONODULO_ROOT": str(root), "BIONODULO_EDITOR_MODE": "0", "BIONODULO_CLOUD_MODE": "0",
        "BIONODULO_SESSION_TOKEN": "", "BIONODULO_PROXY_SECRET": "", "BIONODULO_REDIS_URL": "",
        "BIONODULO_EXECUTION_BACKEND": "local", "BIONODULO_DECLARATIVE_CATALOG": str(catalog),
        "BIONODULO_ALLOW_UNVERIFIED_CWL": "1", "LC_ALL": "C",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("BIONODULO_OCI_RUNTIME_CONFIG", raising=False)
    monkeypatch.setattr(NodeRegistry, "_instance", None)
    from server import create_app

    workflow = {"name": "Pinned UCSC FASTA to 2bit", "nodes": [{
        "id": "convert", "type": node_id,
        "params": {"fasta_file": str(fixture)},
    }], "edges": []}
    with TestClient(create_app()) as client:
        info = client.get("/api/object_info").json()
        assert all(
            info[spec["identity"]["machine_id"]]["declarative_runtime"]["verification"] == "unverified"
            for spec in catalog_specs
        )
        assert info[node_id]["declarative_runtime"]["verification"] == "unverified"
        assert info[node_id]["input"]["required"]["fasta_file"][0] == "FILE"
        validation = client.post("/api/workflow/validate", json={"workflow": workflow})
        assert validation.status_code == 200 and validation.json()["valid"], validation.text
        denied = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert denied.status_code == 200 and not denied.json()["execution_ready"], denied.text
        assert "BIONODULO_OCI_RUNTIME_CONFIG" in json.dumps(denied.json())
        monkeypatch.setenv("BIONODULO_OCI_RUNTIME_CONFIG", str(runtime))
        ready = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert ready.status_code == 200 and ready.json()["execution_ready"], ready.text
        response = client.post("/api/runs", json={"workflow": workflow})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            if details["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.1)
        assert details["status"] == "completed", details
        output = Path(details["result"]["outputs"]["convert"]["twobit_file"])
        assert decode_twobit(output.read_bytes()) == {
            "chrA": "ACGTACGTNNNNACGT", "chrB": "TTGCAANNCC",
        }
        assert fixture.read_bytes() == b">chrA\nACGTACGTNNNNACGT\n>chrB\nTTGCAANNCC\n"
        receipt = details["result"]["metadata"]["cwl_oci"]["convert"]
        assert receipt["image_platform"].endswith("c20b52737a16a2d554e686ae7d1b448d5d2dc5251d23432ab0a381bac1e61a73")
        assert receipt["nodejs_sha256"] == json.loads(runtime.read_text())["nodejs_sha256"]
        assert receipt["resource_cap_cores"] == "2" and receipt["resource_cap_ram_mib"] == "2048"
        assert receipt["container_cleanup_count"] == "0"
        assert any(item["port_id"] == "twobit_file" for item in receipt["output_publication"])
        stderr = next(root.rglob("cwltool.stderr.log")).read_text()
        assert "--net=none" in stderr and "--memory=1024m" in stderr and "--cpus=1" in stderr
        crate = client.get(f"/api/runs/{run_id}/ro-crate")
        assert crate.status_code == 200, crate.text
        action = next(item for item in crate.json()["@graph"] if item.get("@id") == "#run-convert")
        assert action["bionodulo:ociImagePlatform"] == receipt["image_platform"]
        assert action["bionodulo:ociSourceSha256"] == receipt["source_sha256"]
        assert action["bionodulo:ociNodejsSha256"] == receipt["nodejs_sha256"]
        evidence.write_text(json.dumps({
            "catalog_sha256": "sha256:" + hashlib.sha256(catalog_bytes).hexdigest(),
            "catalog_spec_count": len(catalog_specs), "tested_node_id": node_id,
            "workflow": workflow, "discovery": info[node_id],
            "denied_readiness": denied.json(), "ready": ready.json(), "run": details,
            "crate": crate.json(),
        }, indent=2, default=str) + "\n", encoding="utf-8")

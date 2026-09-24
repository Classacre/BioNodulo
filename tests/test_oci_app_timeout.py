"""Opt-in app timeout must remove a running pinned-image container."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bionodulo.nodes.contract.cwl_oci import import_cwl_oci, import_cwl_oci_spec
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.registry import NodeRegistry


pytestmark = pytest.mark.skipif(
    not os.environ.get("BIONODULO_OCI_E2E_CATALOG"),
    reason="explicit isolated OCI app runtime required",
)


def test_queue_timeout_removes_real_container(tmp_path: Path, monkeypatch) -> None:
    reference_catalog = Path(os.environ["BIONODULO_OCI_E2E_CATALOG"])
    runtime = Path(os.environ["BIONODULO_OCI_E2E_RUNTIME"])
    evidence = Path(os.environ["BIONODULO_OCI_E2E_EVIDENCE"])
    source = Path(__file__).parent / "fixtures" / "oci" / "long_sleep.cwl"
    base = NodeSpec.model_validate_json(json.dumps(json.loads(reference_catalog.read_text())["specs"][0]))
    assert base.cwl_oci is not None
    contract = import_cwl_oci(
        source.read_bytes(), source_uri=source.resolve().as_uri(),
        image_index=base.cwl_oci.image_index, image_platform=base.cwl_oci.image_platform,
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    spec = import_cwl_oci_spec(contract, node_id="generated_oci_sleep_timeout_audit")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"schema_version": 1, "specs": [spec.model_dump(mode="json")]}))
    root = tmp_path / "app"
    root.mkdir()
    (root / "bionodulo.json").write_text(json.dumps({"execution": {
        "env_isolation": "auto", "max_workers": 1, "content_hashing": "strong", "timeout_seconds": 6,
    }}))
    for key, value in {
        "BIONODULO_ROOT": str(root), "BIONODULO_EDITOR_MODE": "0", "BIONODULO_CLOUD_MODE": "0",
        "BIONODULO_SESSION_TOKEN": "", "BIONODULO_PROXY_SECRET": "", "BIONODULO_REDIS_URL": "",
        "BIONODULO_EXECUTION_BACKEND": "local", "BIONODULO_DECLARATIVE_CATALOG": str(catalog),
        "BIONODULO_ALLOW_UNVERIFIED_CWL": "1", "BIONODULO_OCI_RUNTIME_CONFIG": str(runtime),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(NodeRegistry, "_instance", None)
    from server import create_app

    workflow = {"name": "Timeout OCI sleep audit", "nodes": [{
        "id": "sleep", "type": "generated_oci_sleep_timeout_audit", "params": {"seconds": 90},
    }], "edges": []}
    with TestClient(create_app()) as client:
        ready = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert ready.status_code == 200 and ready.json()["execution_ready"], ready.text
        created = client.post("/api/runs", json={"workflow": workflow})
        assert created.status_code == 200, created.text
        run_id = created.json()["run_id"]
        attempt_label = None
        observed_ids = ""
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            wrappers = list(root.rglob("docker-cli/docker"))
            if wrappers:
                match = re.search(r"org\.bionodulo\.oci\.attempt=([0-9a-f]{32})", wrappers[0].read_text())
                assert match is not None
                attempt_label = match.group(1)
                observed_ids = subprocess.run(
                    ["/usr/bin/docker", "container", "ls", "-q", "--no-trunc", "--filter",
                     f"label=org.bionodulo.oci.attempt={attempt_label}"],
                    capture_output=True, text=True, timeout=10, check=True,
                ).stdout.strip()
                if observed_ids:
                    break
            time.sleep(0.1)
        assert attempt_label and observed_ids, "app never launched the labeled OCI container"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            remaining = subprocess.run(
                ["/usr/bin/docker", "container", "ls", "-aq", "--no-trunc", "--filter",
                 f"label=org.bionodulo.oci.attempt={attempt_label}"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout.strip()
            if details["status"] not in {"queued", "pending", "running"} and not remaining:
                break
            time.sleep(0.1)
        assert details["status"] == "failed", details
        assert not remaining, "timed-out OCI container remains in the Docker daemon"
        receipts = list(root.rglob("*.failure.json"))
        assert len(receipts) == 1
        failure = json.loads(receipts[0].read_text())
        assert "Timeout" in failure["error_type"]
        evidence.write_text(json.dumps({
            "run_id": run_id, "container_id": observed_ids, "attempt_label": attempt_label,
            "run": details, "failure_receipt": failure,
            "container_absent_after_timeout": not remaining,
        }, indent=2, default=str) + "\n")

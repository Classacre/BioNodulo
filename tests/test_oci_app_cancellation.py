"""Opt-in real queue cancellation must remove a running labeled container."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from bionodulo.nodes.contract.cwl_oci import declared_docker_pull, import_cwl_oci, import_cwl_oci_spec
from bionodulo.nodes.contract.environments import ExecutionPlatform
from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.registry import NodeRegistry


pytestmark = pytest.mark.skipif(
    not os.environ.get("BIONODULO_OCI_E2E_CATALOG"),
    reason="explicit isolated OCI app runtime required",
)


def test_queue_cancellation_removes_real_container(tmp_path: Path, monkeypatch) -> None:
    reference_catalog = Path(os.environ["BIONODULO_OCI_E2E_CATALOG"])
    runtime = Path(os.environ["BIONODULO_OCI_E2E_RUNTIME"])
    evidence = Path(os.environ["BIONODULO_OCI_E2E_EVIDENCE"])
    source = Path(__file__).parent / "fixtures" / "oci" / "long_sleep.cwl"
    source_bytes = source.read_bytes()
    fixture_pull = declared_docker_pull(yaml.safe_load(source_bytes))
    matching = [
        spec for spec in json.loads(reference_catalog.read_text())["specs"]
        if spec.get("cwl_oci", {}).get("source_docker_pull") == fixture_pull
    ]
    assert matching and len({spec["cwl_oci"]["image_platform"] for spec in matching}) == 1
    base = NodeSpec.model_validate_json(json.dumps(matching[0]))
    assert base.cwl_oci is not None
    contract = import_cwl_oci(
        source_bytes, source_uri=source.resolve().as_uri(),
        image_index=base.cwl_oci.image_index, image_platform=base.cwl_oci.image_platform,
        platform=ExecutionPlatform.LINUX_AMD64,
    )
    spec = import_cwl_oci_spec(contract, node_id="generated_oci_sleep_audit")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"schema_version": 1, "specs": [spec.model_dump(mode="json")]}))
    root = tmp_path / "app"
    root.mkdir()
    (root / "bionodulo.json").write_text(json.dumps({"execution": {
        "env_isolation": "auto", "max_workers": 1, "content_hashing": "strong",
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

    workflow = {"name": "Cancel OCI sleep audit", "nodes": [{
        "id": "sleep", "type": "generated_oci_sleep_audit", "params": {"seconds": 90},
    }], "edges": []}
    with TestClient(create_app()) as client:
        ready = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert ready.status_code == 200 and ready.json()["execution_ready"], ready.text
        created = client.post("/api/runs", json={"workflow": workflow})
        assert created.status_code == 200, created.text
        run_id = created.json()["run_id"]
        attempt_label = None
        observed_ids = ""
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            wrappers = list(root.rglob("docker-cli/docker"))
            if wrappers:
                match = re.search(r"org\.bionodulo\.oci\.attempt=([0-9a-f]{32})", wrappers[0].read_text())
                assert match is not None
                attempt_label = match.group(1)
                running = subprocess.run(
                    ["/usr/bin/docker", "container", "ls", "-q", "--no-trunc", "--filter",
                     f"label=org.bionodulo.oci.attempt={attempt_label}"],
                    capture_output=True, text=True, timeout=10, check=True,
                )
                observed_ids = running.stdout.strip()
                if observed_ids:
                    break
            time.sleep(0.1)
        assert attempt_label and observed_ids, "app never launched the labeled OCI container"
        cancelled = client.post(f"/api/queue/{run_id}/cancel")
        assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled", cancelled.text
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            receipts = list(root.rglob("*.failure.json"))
            remaining = subprocess.run(
                ["/usr/bin/docker", "container", "ls", "-aq", "--no-trunc", "--filter",
                 f"label=org.bionodulo.oci.attempt={attempt_label}"],
                capture_output=True, text=True, timeout=10, check=True,
            ).stdout.strip()
            if details["status"] not in {"queued", "pending", "running"} and not remaining and receipts:
                break
            time.sleep(0.1)
        assert details["status"] == "cancelled", details
        assert not remaining, "cancelled OCI container remains in the Docker daemon"
        assert len(receipts) == 1
        failure = json.loads(receipts[0].read_text())
        assert failure["error_type"] in {"CommandCancelledError", "CancelledError"}
        evidence.write_text(json.dumps({
            "run_id": run_id, "container_id": observed_ids, "attempt_label": attempt_label,
            "cancelled": cancelled.json(), "run": details, "failure_receipt": failure,
            "container_absent_after_cancel": not remaining,
        }, indent=2, default=str) + "\n")

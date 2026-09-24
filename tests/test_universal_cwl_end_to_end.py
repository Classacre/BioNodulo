"""Opt-in native integration using unmodified, independently sourced CWL tools.

Set BIONODULO_CWL_E2E_ENVIRONMENT to an actual locked EnvironmentSpec JSON.
No subprocess, registry, queue or output result is mocked. The package/native
execution evidence does not establish container or scientific semantic proof.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.contract.compiler import CatalogCompiler
from bionodulo.nodes.contract.cwl import import_cwl
from bionodulo.nodes.contract.environments import EnvironmentSpec
from bionodulo.nodes.registry import NodeRegistry


pytestmark = pytest.mark.skipif(
    not os.environ.get("BIONODULO_CWL_E2E_ENVIRONMENT"),
    reason="explicit native CWL runtime lock required",
)
FIXTURES = Path(__file__).parent / "fixtures" / "cwl-upstream"


def evidence(name, payload):
    if root := os.environ.get("BIONODULO_CWL_E2E_EVIDENCE"):
        target = Path(root)
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def imported(filename, node_id):
    environment = TypeAdapter(EnvironmentSpec).validate_json(
        Path(os.environ["BIONODULO_CWL_E2E_ENVIRONMENT"]).read_bytes()
    )
    source = FIXTURES / filename
    provenance = next(item for item in json.loads((FIXTURES / "manifest.json").read_text())["files"]
                      if item["file"] == filename)
    raw_source = source.read_bytes()
    source_digest = "sha256:" + hashlib.sha256(raw_source).hexdigest()
    assert source_digest == provenance["sha256"]
    document = yaml.safe_load(raw_source.decode("utf-8"))
    return import_cwl(document, node_id=node_id, environment=environment,
                      tool_id="coreutils", tool_version="9.5", source_uri=provenance["source_url"],
                      source_content_sha256=source_digest, source_size_bytes=len(raw_source))


def native_engine(root, registry):
    return WorkflowExecutor(workspace_dir=root, registry=registry, settings=SimpleNamespace(
        execution=SimpleNamespace(max_workers=1, env_isolation="off", content_hashing="strong"),
        api_secrets={},
    ))


def test_unmodified_upstream_cat_preserves_binary_file_and_environment_drift_fails(tmp_path):
    candidate = imported("cat3-nodocker.cwl", "upstream_binary_cat")
    registry = NodeRegistry.create_isolated()
    registry.register_cwl_spec(candidate, allow_unverified=True)
    original = bytes(range(256)) * 4096
    source = tmp_path / "binary input.bin"
    source.write_bytes(original)
    workflow = {"nodes": [{"id": "copy", "type": candidate.identity.machine_id,
                            "params": {"file1": str(source)}}], "edges": []}
    engine = native_engine(tmp_path / "engine", registry)
    try:
        result = asyncio.run(engine.execute("binary", workflow))
        assert result["status"] == "completed", result
        output = Path(result["outputs"]["copy"]["output_file"])
        assert output.read_bytes() == original
        rerun = asyncio.run(engine.execute("repeat", workflow))
        assert rerun["node_results"]["copy"]["status"] == "completed", rerun
        # A stale expected binary digest must fail even though this workflow
        # previously succeeded. Only data changes; no runtime/tool code changes.
        probe = next(item for item in candidate.environment.executable_probes if Path(item.locator).name == "cat")
        corrupted = probe.model_copy(update={"fingerprint": "sha256:" + "0" * 64})
        modified_environment = candidate.environment.model_copy(update={"executable_probes": tuple(
            corrupted if item.probe_id == probe.probe_id else item
            for item in candidate.environment.executable_probes
        )})
        changed = candidate.model_copy(update={"environment": modified_environment})
        changed_registry = NodeRegistry.create_isolated()
        changed_registry.register_cwl_spec(changed, allow_unverified=True)
        changed_engine = native_engine(tmp_path / "engine", changed_registry)
        try:
            failure = asyncio.run(changed_engine.execute("wrong-runtime", workflow))
            assert failure["status"] == "failed", failure
            assert not failure["outputs"]
            assert any(word in failure["node_results"]["copy"]["error"].lower()
                       for word in ("fingerprint", "sha256", "digest"))
        finally:
            changed_engine.cache.close()
        source.write_bytes(original + b"x")
        oversized = asyncio.run(engine.execute("oversized-stdout", workflow))
        assert oversized["status"] == "failed", oversized
        assert not oversized["outputs"]
        assert "1048576-byte output limit" in oversized["node_results"]["copy"]["error"]
        assert source.read_bytes() == original + b"x"
        evidence("upstream-binary-and-drift", {"result": result, "rerun": rerun, "failure": failure,
                 "oversized_output": oversized,
                 "expected_sha256": hashlib.sha256(original).hexdigest(),
                 "contract_digest": candidate.contract_digest()})
    finally:
        engine.cache.close()


def test_two_upstream_descriptors_compile_discover_and_execute_through_api_queue(tmp_path, monkeypatch):
    cat = imported("cat3-nodocker.cwl", "upstream_cat")
    sort = imported("sorttool.cwl", "upstream_sort")
    compiled = CatalogCompiler().compile((cat, sort))
    bundle = tmp_path / "catalog.json"
    bundle.write_text(json.dumps({"schema_version": 1, "specs": [spec.model_dump(mode="json") for spec in (cat, sort)]}))
    root = tmp_path / "app"
    root.mkdir()
    (root / "bionodulo.json").write_text(json.dumps({"execution": {
        "env_isolation": "auto", "max_workers": 1, "content_hashing": "strong",
    }}))
    for key, value in {
        "BIONODULO_ROOT": str(root), "BIONODULO_EDITOR_MODE": "0", "BIONODULO_CLOUD_MODE": "0",
        "BIONODULO_SESSION_TOKEN": "", "BIONODULO_PROXY_SECRET": "", "BIONODULO_REDIS_URL": "",
        "BIONODULO_EXECUTION_BACKEND": "local", "BIONODULO_DECLARATIVE_CATALOG": str(bundle),
        "BIONODULO_ALLOW_UNVERIFIED_CWL": "1", "LC_ALL": "C",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(NodeRegistry, "_instance", None)
    from server import create_app
    source = root / "input lines.txt"
    source.write_bytes(b"zeta\nalpha\nmu\nalpha\n")
    workflow = {
        "name": "Imported CWL composition", "nodes": [
            {"id": "copy", "type": "upstream_cat", "params": {"file1": str(source)}},
            {"id": "ordered", "type": "upstream_sort", "params": {"reverse": True}},
        ], "edges": [{"source": "copy", "source_output": "output_file", "target": "ordered", "target_input": "input"}],
    }
    with TestClient(create_app()) as client:
        info = client.get("/api/object_info").json()
        assert info["upstream_sort"]["input"]["required"]["reverse"][0] == "BOOLEAN"
        assert info["upstream_cat"]["output_name"] == ["output_file"]
        assert info["upstream_cat"]["declarative_runtime"]["verification"] == "unverified"
        validation = client.post("/api/workflow/validate", json={"workflow": workflow})
        assert validation.status_code == 200 and validation.json()["valid"], validation.text
        readiness = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert readiness.status_code == 200, readiness.text
        assert readiness.json()["execution_ready"], readiness.text
        configured_prefixes = os.environ["BIONODULO_CWL_ENVIRONMENTS"]
        monkeypatch.setenv("BIONODULO_CWL_ENVIRONMENTS", "{}")
        unavailable = client.post("/api/manager/resolve", json={"workflow": workflow})
        assert unavailable.status_code == 200 and not unavailable.json()["execution_ready"], unavailable.text
        monkeypatch.setenv("BIONODULO_CWL_ENVIRONMENTS", configured_prefixes)
        response = client.post("/api/runs", json={"workflow": workflow})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            if details["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.05)
        assert details["status"] == "completed", details
        output = Path(details["result"]["outputs"]["ordered"]["output"])
        assert output.read_bytes() == b"zeta\nmu\nalpha\nalpha\n"
        assert source.read_bytes() == b"zeta\nalpha\nmu\nalpha\n"
        crate = client.get(f"/api/runs/{run_id}/ro-crate")
        assert crate.status_code == 200
        assert details["result"]["metadata"]["semantics"]["verification"] == "unverified"
        for name, candidate in (("copy", cat), ("ordered", sort)):
            invocation = candidate.cwl_invocation
            receipt = details["result"]["metadata"]["declarative_cwl"][name]
            assert receipt["source_content_sha256"] == invocation.source_content_sha256
            assert receipt["source_size_bytes"] == invocation.source_size_bytes
            assert receipt["descriptor_digest"] == invocation.descriptor_sha256
        evidence("upstream-api-queue-composition", {"catalog_digest": compiled.catalog_digest,
                 "workflow": workflow, "run": details, "crate": crate.json(),
                 "readiness": readiness.json(), "missing_prefix_readiness": unavailable.json(),
                 "metadata": {name: info[name] for name in ("upstream_cat", "upstream_sort")}})


def test_third_upstream_tool_runs_without_a_new_adapter(tmp_path):
    candidate = imported("echo-file-tool.cwl", "upstream_echo")
    registry = NodeRegistry.create_isolated()
    registry.register_cwl_spec(candidate, allow_unverified=True)
    engine = native_engine(tmp_path / "engine", registry)
    try:
        result = asyncio.run(engine.execute("third-tool", {"nodes": [{
            "id": "echo", "type": "upstream_echo", "params": {"in": "literal ; & $ symbols", "name": "unused"},
        }], "edges": []}))
        assert result["status"] == "completed", result
        assert Path(result["outputs"]["echo"]["out"]).read_bytes() == b"literal ; & $ symbols\n"
        evidence("third-upstream-tool", result)
    finally:
        engine.cache.close()


def test_success_exit_with_wrong_output_contract_is_rejected(tmp_path):
    reference = imported("cat3-nodocker.cwl", "reference_copy")
    document = yaml.safe_load((FIXTURES / "cat3-nodocker.cwl").read_text())
    document.pop("stdout")
    document["outputs"]["output_file"]["outputBinding"]["glob"] = "never-created.txt"
    candidate = import_cwl(document, node_id="incorrect_mapping", environment=reference.environment,
                           tool_id="coreutils", tool_version="9.5", source_uri=(tmp_path / "wrong.cwl").as_uri())
    registry = NodeRegistry.create_isolated()
    registry.register_cwl_spec(candidate, allow_unverified=True)
    source = tmp_path / "small.txt"
    source.write_text("successful stdout does not establish an output contract\n")
    engine = native_engine(tmp_path / "engine", registry)
    try:
        result = asyncio.run(engine.execute("missing-output", {"nodes": [{
            "id": "copy", "type": "incorrect_mapping", "params": {"file1": str(source)},
        }], "edges": []}))
        assert result["status"] == "failed", result
        assert not result["outputs"]
        assert "never-created" in result["node_results"]["copy"]["error"]
        evidence("wrong-output-mapping-rejected", result)
    finally:
        engine.cache.close()

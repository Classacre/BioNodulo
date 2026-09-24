"""Real application executor/API tests: synthetic public-format fixtures, no mocked tools.

These test bounded scientific functionality, not every node or PhD aim. The
FastAPI TestClient runs the actual lifespan, queue, registry and executor.
Only environment configuration is isolated; no execution result is mocked.
"""
from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.provenance.workflow_embed import extract_workflow
from bionodulo.workflow.semantic_checks import check_workflow_semantics


def evidence(name, payload):
    destination = os.environ.get("BIONODULO_PHD_EVIDENCE")
    if destination:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def executor(root):
    return WorkflowExecutor(
        workspace_dir=root, registry=NodeRegistry.create_isolated(),
        settings=SimpleNamespace(execution=SimpleNamespace(max_workers=1, env_isolation="off", content_hashing="strong"), api_secrets={}),
    )


def normalization(table, method="cpm"):
    return {"name": "CPM fixture", "nodes": [{"id": "norm", "type": "normalize_data", "params": {
        "table": str(table), "method": method, "id_columns": "gene",
    }}], "edges": []}


def read_table(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def test_real_count_pipeline_cache_integrity_and_run_crate(tmp_path):
    table = tmp_path / "counts.tsv"
    raw = b"gene\ts1\ts2\ngeneA\t3\t1\ngeneB\t1\t3\n"
    table.write_bytes(raw)
    workflow = normalization(table)
    workflow["nodes"].append({"id": "select", "type": "extract_columns", "params": {"columns": "gene,s1"}})
    workflow["edges"] = [{"id": "norm-select", "source": "norm", "source_output": "normalized_table", "target": "select", "target_input": "table"}]
    engine = executor(tmp_path / "engine")
    result = asyncio.run(engine.execute("counts", workflow))
    assert result["status"] == "completed", result
    path = Path(result["outputs"]["select"]["extracted_table"])
    assert read_table(path) == [{"gene": "geneA", "s1": "750000"}, {"gene": "geneB", "s1": "250000"}]
    assert table.read_bytes() == raw
    assert b"<!--" not in path.read_bytes()
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    cached = asyncio.run(engine.execute("counts-cached", workflow))
    assert cached["status"] == "completed"
    assert all(record["status"] == "cached" for record in cached["node_results"].values())
    assert set(cached["metadata"]["nodes"]) == {"norm", "select"}
    assert all(record["status"] == "cached" for record in cached["metadata"]["nodes"].values())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert extract_workflow(path)["workflow"]["name"] == workflow["name"]
    crate_path = tmp_path / "engine/runs/counts/ro-crate/ro-crate-metadata.json"
    crate = json.loads(crate_path.read_text())
    entities = {entity["@id"]: entity for entity in crate["@graph"]}
    output_entity = entities[path.resolve().as_uri()]
    assert output_entity["bionodulo:sha256"] == original_hash
    assert entities["#run-select"]["result"] == [{"@id": path.resolve().as_uri()}]
    assert entities["#workflow-run"]["actionStatus"] == "CompletedActionStatus"
    assert result["metadata"]["semantics"]["verification"] == "unverified"
    evidence("counts-pipeline", {"result": result, "cached": cached, "rows": read_table(path), "crate": crate, "sha256": original_hash})


@pytest.mark.parametrize("case,values,method,expected", [
    ("nan", "nan\t1\ngeneB\t1\t3", "cpm", "finite"),
    ("infinity", "inf\t1\ngeneB\t1\t3", "cpm", "finite"),
    ("negative_counts", "-3\t1\ngeneB\t1\t3", "cpm", "non-negative"),
    ("zero_library", "0\t1\ngeneB\t0\t3", "cpm", "positive finite"),
    ("tpm_without_lengths", "3\t1\ngeneB\t1\t3", "tpm_from_counts", "lengths"),
])
def test_real_normalization_rejects_silent_errors(tmp_path, case, values, method, expected):
    table = tmp_path / "invalid.tsv"
    table.write_text("gene\ts1\ts2\ngeneA\t" + values + "\n")
    result = asyncio.run(executor(tmp_path / "engine").execute(case, normalization(table, method), force=True))
    assert result["status"] == "failed"
    assert expected in result["node_results"]["norm"]["error"]
    assert result["metadata"]["nodes"]["norm"]["status"] == "failed"
    assert expected in result["metadata"]["nodes"]["norm"]["error"]
    assert result["outputs"] == {}
    crate = json.loads((tmp_path / f"engine/runs/{case}/ro-crate/ro-crate-metadata.json").read_text())
    assert next(e for e in crate["@graph"] if e["@id"] == "#run-norm")["actionStatus"] == "FailedActionStatus"
    evidence(case, {"result": result, "crate": crate})


def test_real_quantile_normalization_preserves_tied_values(tmp_path):
    table = tmp_path / "ties.tsv"
    table.write_text("gene\ts1\ts2\nA\t5\t4\nB\t5\t1\nC\t9\t3\n")
    result = asyncio.run(executor(tmp_path / "engine").execute("ties", normalization(table, "quantile")))
    assert result["status"] == "completed"
    rows = read_table(result["outputs"]["norm"]["normalized_table"])
    assert [float(row["s1"]) for row in rows] == [3.5, 3.5, 6.5]
    assert [float(row["s2"]) for row in rows] == [6.5, 3, 4]
    evidence("quantile-ties", {"result": result, "rows": rows})


def planted(table, *, widgets=False, alternate=False):
    workflow = normalization(table)
    if widgets:
        workflow["nodes"][0]["params"]["method"] = "z_score"
        workflow["nodes"][0]["widgets"] = {"method": "cpm"}
    workflow["nodes"].append({"id": "de", "type": "deseq2", "params": {"sample_info": str(table)}})
    workflow["edges"] = ([{"id": "bad", "source": "norm", "source_output": "normalized_table", "target": "de", "target_input": "count_matrix"}] if alternate else
                         [{"id": "bad", "from": {"node": "norm", "output": "normalized_table"}, "to": {"node": "de", "input": "count_matrix"}}])
    return workflow


@pytest.mark.parametrize("widgets,alternate", [(False, False), (False, True), (True, True)])
def test_executor_rejects_incompatible_contract_before_any_execution(tmp_path, widgets, alternate):
    workflow = planted(tmp_path / "not-needed.tsv", widgets=widgets, alternate=alternate)
    result = asyncio.run(executor(tmp_path / "engine").execute("rejected", workflow))
    assert result["status"] == "failed"
    assert result["node_results"] == {}
    assert result["semantics"]["verification"] == "violated"
    assert result["semantics"]["checks"][0]["observed"] == "cpm"
    assert not (tmp_path / "engine/runs/rejected").exists()
    evidence(f"executor-contract-{widgets}-{alternate}", result)


def test_real_biopython_translation_and_protein_stats(tmp_path):
    from Bio import __version__ as bio_version
    fasta = tmp_path / "coding.fasta"
    original = ">proteinA\nATGGCTTTTTAA\n>proteinB\nATGGGTTGA\n"
    fasta.write_text(original)
    workflow = {"name": "known translation", "nodes": [
        {"id": "translate", "type": "bp_translate", "params": {"input_file": str(fasta), "table": "Standard", "to_stop": True}},
        {"id": "stats", "type": "bp_seq_stats", "params": {"sequence_type": "protein", "format": "fasta"}},
    ], "edges": [{"from": {"node": "translate", "output": "protein_fasta"}, "to": {"node": "stats", "input": "input_file"}}]}
    result = asyncio.run(executor(tmp_path / "engine").execute("translation", workflow))
    assert result["status"] == "completed", result
    proteins = Path(result["outputs"]["translate"]["protein_fasta"]).read_text()
    assert "MAF\n" in proteins and "MG\n" in proteins
    stats = json.loads(Path(result["outputs"]["stats"]["stats_json"]).read_text())
    assert isinstance(stats, list), "Provenance must not wrap the JSON array"
    assert [record["length"] for record in stats] == [3, 2]
    assert all(record["gc_content"] is None for record in stats)
    assert fasta.read_text() == original
    evidence("biopython-translation", {"biopython_version": bio_version, "workflow": workflow, "result": result, "proteins": proteins, "stats": stats})


def test_real_api_rejects_contract_and_executes_positive_control(tmp_path, monkeypatch):
    for key, value in {"BIONODULO_ROOT": str(tmp_path / "api"), "BIONODULO_EDITOR_MODE": "0", "BIONODULO_CLOUD_MODE": "0", "BIONODULO_SESSION_TOKEN": "", "BIONODULO_PROXY_SECRET": "", "BIONODULO_REDIS_URL": "", "BIONODULO_EXECUTION_BACKEND": "local", "BIONODULO_EXECUTION__ON_INTERRUPT": "manual"}.items():
        monkeypatch.setenv(key, value)
    from server import create_app
    table = tmp_path / "counts.tsv"
    table.write_text("gene\ts1\ts2\nA\t3\t1\nB\t1\t3\n")
    with TestClient(create_app()) as client:
        invalid = planted(table, alternate=True)
        validation = client.post("/api/workflow/validate", json={"workflow": invalid})
        assert validation.status_code == 200
        assert validation.json()["valid"] is False
        assert "normalization_state" in " ".join(validation.json()["errors"])
        rejected = client.post("/api/runs", json={"workflow": invalid})
        assert rejected.status_code == 400
        positive = normalization(table)
        positive["nodes"].append({**positive["nodes"][0], "id": "norm_cached"})
        response = client.post("/api/runs", json={"workflow": positive})
        assert response.status_code == 200, response.text
        run_id = response.json()["run_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            details = client.get(f"/api/runs/{run_id}").json()
            if details["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.05)
        assert details["status"] == "completed", details
        assert all(node["status"] == "completed" for node in details["result"]["node_results"].values())
        crate = client.get(f"/api/runs/{run_id}/ro-crate")
        assert crate.status_code == 200, crate.text
        manifest = client.get(f"/api/runs/{run_id}/manifest")
        assert manifest.status_code == 200
        repeat = client.post("/api/runs", json={"workflow": positive, "force_nodes": ["norm"]})
        assert repeat.status_code == 200, repeat.text
        repeat_id = repeat.json()["run_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            repeated = client.get(f"/api/runs/{repeat_id}").json()
            if repeated["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.05)
        assert repeated["status"] == "completed", repeated
        expected_statuses = {"norm": "completed", "norm_cached": "cached"}
        assert {node: record["status"] for node, record in repeated["result"]["node_results"].items()} == expected_statuses
        assert {node: record["status"] for node, record in repeated["result"]["metadata"]["nodes"].items()} == expected_statuses
        assert {node["node_id"]: node["status"] for node in repeated["node_statuses"]} == expected_statuses
        assert set(repeated["execution_plan"]) == set(expected_statuses)
        evidence("api-queue-executor", {"validation": validation.json(), "rejection": rejected.json(), "run": details, "repeat_run": repeated, "crate": crate.json(), "manifest": manifest.json()})
        # A real runtime error must be present in all progress projections,
        # rather than silently disappearing from the top-level node summary.
        bad_table = tmp_path / "negative-counts.tsv"
        bad_table.write_text("gene\ts1\ts2\nA\t-3\t1\nB\t1\t3\n")
        failed_response = client.post("/api/runs", json={"workflow": normalization(bad_table)})
        assert failed_response.status_code == 200, failed_response.text
        failed_id = failed_response.json()["run_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            failed = client.get(f"/api/runs/{failed_id}").json()
            if failed["status"] not in {"queued", "pending", "running"}:
                break
            time.sleep(0.05)
        assert failed["status"] == "failed", failed
        assert failed["result"]["metadata"]["nodes"]["norm"]["status"] == "failed"
        assert {node["node_id"]: node["status"] for node in failed["node_statuses"]} == {"norm": "failed"}
        evidence("api-runtime-failure-progress", failed)


def test_unknown_input_state_is_explicitly_unverified():
    result = check_workflow_semantics({"nodes": [{"id": "input", "type": "input_bam"}, {"id": "index", "type": "samtools_index"}], "edges": [{"source": "input", "source_output": "bam", "target": "index", "target_input": "bam"}]})
    assert result.ok
    assert result.to_dict()["verification"] == "unverified"
    assert result.checks[0]["status"] == "unverified"

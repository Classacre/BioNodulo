from __future__ import annotations

import builtins
import json

import pytest
from fastapi.testclient import TestClient


def test_workflow_import_rejects_unavailable_converter_instead_of_placeholder_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from server import create_app

    real_import = builtins.__import__

    def import_with_missing_converter(
        name: str,
        globals: dict[str, object] | None = None,
        locals: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "bionodulo.converter.snakemake_converter":
            raise ImportError("simulated missing converter")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_with_missing_converter)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/workflow/import",
            json={"source": "snakemake", "content": "rule all:\n    shell: \"echo ok\""},
        )

    assert response.status_code == 500
    assert "Converter for snakemake is unavailable" in response.json()["detail"]


def test_settings_routes_redact_secret_like_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    with TestClient(create_app()) as client:
        save_response = client.post(
            "/api/settings",
            json={
                "settings": {
                    "bionodulo.llm.apiKey": "secret-key",
                    "visible": "sample",
                    "nested": {"password": "secret-password"},
                }
            },
        )
        all_response = client.get("/api/settings")
        single_response = client.get("/api/settings/bionodulo.llm.apiKey")

    assert save_response.status_code == 200
    assert all_response.status_code == 200
    payload = all_response.json()
    assert payload["bionodulo.llm.apiKey"] == "***"
    assert payload["visible"] == "sample"
    assert payload["nested"]["password"] == "***"
    assert "secret-key" not in json.dumps(payload)
    assert "secret-password" not in json.dumps(payload)
    assert single_response.status_code == 200
    assert single_response.json()["bionodulo.llm.apiKey"] == "***"


def test_checkpoint_manifest_endpoint_returns_empty_manifest_for_new_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    with TestClient(create_app()) as client:
        response = client.get("/api/checkpoints/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["exists"] is False
    assert payload["manifest_path"] == str(tmp_path / "checkpoints" / "checkpoint_manifest.json")
    assert payload["manifest"] == {
        "version": "1.0",
        "checkpoints": {},
        "latest_by_name": {},
        "latest_by_run_node": {},
    }


def test_checkpoint_resolve_endpoint_finds_checkpoint_by_run_node_or_name(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint_file = checkpoint_dir / "after_annotation.json"
    checkpoint_file.write_text('{"data":{"records":12}}', encoding="utf-8")
    entry = {
        "checkpoint_name": "after_annotation",
        "checkpoint_path": str(checkpoint_file),
        "timestamp": 1.0,
        "timestamp_iso": "2026-06-05T00:00:00Z",
        "compressed": False,
        "size_bytes": checkpoint_file.stat().st_size,
        "run_id": "run-42",
        "node_id": "checkpoint-node",
        "node_type": "variant_annotation",
    }
    (checkpoint_dir / "checkpoint_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "checkpoints": {str(checkpoint_file): entry},
                "latest_by_name": {"after_annotation": entry},
                "latest_by_run_node": {"run-42:checkpoint-node": entry},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        by_run_node = client.get(
            "/api/checkpoints/resolve",
            params={"run_id": "run-42", "node_id": "checkpoint-node"},
        )
        by_name = client.get(
            "/api/checkpoints/resolve",
            params={"checkpoint_name": "after_annotation"},
        )

    assert by_run_node.status_code == 200
    assert by_run_node.json()["found"] is True
    assert by_run_node.json()["checkpoint"] == entry
    assert by_name.status_code == 200
    assert by_name.json()["found"] is True
    assert by_name.json()["checkpoint"] == entry


def test_checkpoint_runtime_api_reports_downstream_resume_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint_file = checkpoint_dir / "after_annotation.json"
    checkpoint_file.write_text('{"data":{"records":12}}', encoding="utf-8")
    entry = {
        "checkpoint_name": "after_annotation",
        "checkpoint_path": str(checkpoint_file),
        "timestamp": 1.0,
        "timestamp_iso": "2026-06-05T00:00:00Z",
        "compressed": False,
        "size_bytes": checkpoint_file.stat().st_size,
        "run_id": "run-42",
        "node_id": "checkpoint-node",
        "node_type": "variant_annotation",
        "resume_manifest_supported": True,
        "resume_supported": True,
        "note": "Checkpoint artifact and resume manifest written; downstream executor resume is supported for checkpoint nodes.",
    }
    (checkpoint_dir / "checkpoint_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "checkpoints": {str(checkpoint_file): entry},
                "latest_by_name": {"after_annotation": entry},
                "latest_by_run_node": {"run-42:checkpoint-node": entry},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        manifest_response = client.get("/api/checkpoints/manifest")
        resolve_response = client.get(
            "/api/checkpoints/resolve",
            params={"checkpoint_name": "after_annotation"},
        )

    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["resume_manifest_supported"] is True
    assert manifest["resume_supported"] is True
    assert "downstream executor resume" in manifest["resume_note"]
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved["resume_manifest_supported"] is True
    assert resolved["resume_supported"] is True
    assert "downstream executor resume" in resolved["resume_note"]
    assert resolved["checkpoint"]["resume_supported"] is True


def test_run_create_forwards_resolved_resume_checkpoint_to_queue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    checkpoint_file = checkpoint_dir / "after_annotation.json"
    checkpoint_file.write_text('{"version":"1.0","data":{"records":12}}', encoding="utf-8")
    entry = {
        "checkpoint_name": "after_annotation",
        "checkpoint_path": str(checkpoint_file),
        "timestamp": 1.0,
        "timestamp_iso": "2026-06-05T00:00:00Z",
        "compressed": False,
        "size_bytes": checkpoint_file.stat().st_size,
        "run_id": "run-42",
        "node_id": "checkpoint-node",
        "node_type": "checkpoint",
    }
    (checkpoint_dir / "checkpoint_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "checkpoints": {str(checkpoint_file): entry},
                "latest_by_name": {"after_annotation": entry},
                "latest_by_run_node": {"run-42:checkpoint-node": entry},
            }
        ),
        encoding="utf-8",
    )

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs.get("run_id", "queued"))

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        queue = Queue()
        client.app.state.run_queue = queue
        response = client.post(
            "/api/runs",
            json={
                "name": "Resume Workflow",
                "workflow": {
                    "name": "Resume Workflow",
                    "nodes": [{"id": "checkpoint-node", "type": "checkpoint"}],
                    "edges": [],
                },
                "resume_checkpoint": {"checkpoint_name": "after_annotation"},
            },
        )

    assert response.status_code == 200
    assert queue.submit_calls
    options = queue.submit_calls[0]["options"]
    assert options["resume_checkpoint"] == entry


def test_hpc_submit_forwards_runtime_parameters_to_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    class RecordingHPC:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def submit_workflow(self, **kwargs: object) -> str:
            self.calls.append(kwargs)
            return "remote-42"

    backend = RecordingHPC()
    with TestClient(create_app()) as client:
        client.app.state.hpc_backend = backend
        response = client.post(
            "/api/hpc/submit",
            json={
                "workflow": {
                    "id": "wf-1",
                    "name": "Parameterized",
                    "nodes": [],
                    "edges": [],
                    "parameters": [{"name": "sample_id", "type": "STRING"}],
                },
                "workflow_id": "wf-1",
                "name": "Parameterized",
                "parameters": {"sample_id": "S1"},
            },
        )

    assert response.status_code == 200
    assert response.json()["remote_job_id"] == "remote-42"
    assert backend.calls[0]["parameters"] == {"sample_id": "S1"}


def test_hpc_submit_rejects_parameterized_run_when_backend_cannot_accept_parameters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    class FixedSignatureHPC:
        async def submit_workflow(
            self,
            *,
            workflow: dict[str, object],
            name: str,
            cpus: int | None,
            memory: str | None,
            walltime: str | None,
            dependency_jobs: list[str],
        ) -> str:
            return "remote-42"

    with TestClient(create_app()) as client:
        client.app.state.hpc_backend = FixedSignatureHPC()
        response = client.post(
            "/api/hpc/submit",
            json={
                "workflow": {
                    "id": "wf-1",
                    "name": "Parameterized",
                    "nodes": [],
                    "edges": [],
                    "parameters": [{"name": "sample_id", "type": "STRING"}],
                },
                "workflow_id": "wf-1",
                "name": "Parameterized",
                "parameters": {"sample_id": "S1"},
            },
        )

    assert response.status_code == 501
    assert response.json()["detail"] == "HPC backend submit_workflow does not support runtime parameters"


def test_hpc_submit_rejects_backend_without_submit_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    class JobOnlyHPC:
        async def submit_job(self, script: str) -> str:
            return f"job-{script}"

    with TestClient(create_app()) as client:
        client.app.state.hpc_backend = JobOnlyHPC()
        response = client.post(
            "/api/hpc/submit",
            json={
                "workflow": {
                    "id": "wf-1",
                    "name": "Workflow Submit",
                    "nodes": [],
                    "edges": [],
                },
                "workflow_id": "wf-1",
                "name": "Workflow Submit",
            },
        )

    assert response.status_code == 501
    assert response.json()["detail"] == "HPC backend submit_workflow is not implemented"


def test_run_create_dry_run_returns_preview_without_queue_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    class PreviewExecutor:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def dry_run(self, **kwargs: object) -> dict[str, object]:
            self.calls.append(kwargs)
            return {
                "status": "dry_run",
                "run_id": kwargs["run_id"],
                "workflow_name": "Dry Run Workflow",
                "execution_order": ["node-a"],
                "nodes": [
                    {
                        "node_id": "node-a",
                        "node_type": "generic_command",
                        "command": ["echo", "hello"],
                        "planned_outputs": {"output": "/tmp/out.txt"},
                    }
                ],
            }

    class Queue:
        def __init__(self) -> None:
            self.executor = PreviewExecutor()
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs.get("run_id", "queued"))

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        queue = Queue()
        client.app.state.run_queue = queue
        response = client.post(
            "/api/runs",
            json={
                "name": "Dry Run Workflow",
                "dry_run": True,
                "workflow": {
                    "name": "Dry Run Workflow",
                    "nodes": [{"id": "node-a", "type": "generic_command", "outputs": {"output": {}}}],
                    "edges": [],
                },
                "parameters": {"sample": "S1"},
                "target_nodes": ["node-a"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "dry_run"
    assert payload["workflow_name"] == "Dry Run Workflow"
    assert payload["execution_order"] == ["node-a"]
    assert payload["nodes"][0]["command"] == ["echo", "hello"]
    assert queue.submit_calls == []
    assert queue.executor.calls
    assert queue.executor.calls[0]["options"] == {
        "parameters": {"sample": "S1"},
        "target_nodes": ["node-a"],
    }


def test_run_manifest_uses_persisted_artifacts_when_queue_result_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    artifact_path = tmp_path / "runs" / "run-42" / "writer" / "result.txt"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text("persisted artifact\n", encoding="utf-8")
    persisted_artifacts = [
        {
            "node_id": "writer",
            "node_type": "file_writer",
            "port": "out",
            "path": str(artifact_path),
            "size": artifact_path.stat().st_size,
        }
    ]
    metadata_path = tmp_path / "runs" / "run-42" / "run_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "run_id": "run-42",
                "status": "completed",
                "forced": False,
                "target_nodes": [],
                "workflow_parameters": {},
                "nodes": {
                    "writer": {
                        "type": "file_writer",
                        "status": "completed",
                        "cache_key": None,
                    }
                },
                "artifacts": persisted_artifacts,
            }
        ),
        encoding="utf-8",
    )

    class EmptyQueue:
        def get_run(self, _run_id: str) -> None:
            return None

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        client.app.state.run_queue = EmptyQueue()
        response = client.get("/api/runs/run-42/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution"]["run_id"] == "run-42"
    assert payload["artifacts"] == persisted_artifacts


def test_pause_requests_endpoint_lists_persisted_requests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    pause_dir = tmp_path / "pause_requests"
    pause_dir.mkdir()
    pause_file = pause_dir / "pause-node.json"
    pause_file.write_text(
        json.dumps(
            {
                "run_id": "run-42",
                "node_id": "pause-node",
                "message": "Review before annotation.",
                "status": "waiting",
                "approved": True,
                "created_at": 1.0,
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/pause_requests")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["errors"] == []
    assert payload["pause_requests"][0]["pause_file"] == str(pause_file)
    assert payload["pause_requests"][0]["node_id"] == "pause-node"
    assert payload["pause_requests"][0]["status"] == "waiting"


def test_pause_requests_endpoint_reports_blocking_runtime_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    pause_dir = tmp_path / "pause_requests"
    pause_dir.mkdir()
    pause_file = pause_dir / "pause-node.json"
    pause_file.write_text(
        json.dumps(
            {
                "run_id": "run-42",
                "node_id": "pause-node",
                "message": "Review before annotation.",
                "status": "waiting",
                "approved": True,
                "created_at": 1.0,
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/pause_requests")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_decision_supported"] is True
    assert payload["engine_pause_supported"] is True
    assert "executor-level blocking pause/resume are supported" in payload["pause_note"]
    assert payload["pause_requests"][0]["pause_file"] == str(pause_file)
    assert payload["pause_requests"][0]["review_decision_supported"] is True
    assert payload["pause_requests"][0]["engine_pause_supported"] is True
    assert "executor-level blocking pause/resume is supported" in payload["pause_requests"][0]["note"]


def test_pause_request_resolve_endpoint_updates_workspace_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    pause_dir = tmp_path / "pause_requests"
    pause_dir.mkdir()
    pause_file = pause_dir / "pause-node.json"
    pause_file.write_text(
        json.dumps(
            {
                "run_id": "run-42",
                "node_id": "pause-node",
                "message": "Review before annotation.",
                "status": "waiting",
                "approved": True,
                "created_at": 1.0,
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/pause_requests/resolve",
            json={
                "node_id": "pause-node",
                "action": "reject",
                "reviewer": "ana",
                "comment": "Variant QC failed",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    saved = json.loads(pause_file.read_text(encoding="utf-8"))
    assert payload["pause_request"]["pause_file"] == str(pause_file)
    assert payload["pause_request"]["status"] == "rejected"
    assert payload["pause_request"]["approved"] is False
    assert payload["pause_request"]["resolved_by"] == "ana"
    assert payload["pause_request"]["resolution_comment"] == "Variant QC failed"
    assert payload["pause_request"]["review_decision_supported"] is True
    assert payload["pause_request"]["engine_pause_supported"] is True
    assert "executor-level blocking pause/resume is supported" in payload["pause_request"]["note"]
    assert saved["status"] == "rejected"
    assert saved["approved"] is False


def test_pause_request_resolve_endpoint_updates_request_by_run_and_node(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    pause_dir = tmp_path / "pause_requests"
    pause_dir.mkdir()
    pause_file = pause_dir / "run-42__pause-node.json"
    pause_file.write_text(
        json.dumps(
            {
                "run_id": "run-42",
                "node_id": "pause-node",
                "message": "Review before annotation.",
                "status": "waiting",
                "approved": True,
                "created_at": 1.0,
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/pause_requests/resolve",
            json={
                "run_id": "run-42",
                "node_id": "pause-node",
                "action": "approve",
                "reviewer": "ana",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    saved = json.loads(pause_file.read_text(encoding="utf-8"))
    assert payload["pause_request"]["pause_file"] == str(pause_file)
    assert payload["pause_request"]["status"] == "approved"
    assert payload["pause_request"]["approved"] is True
    assert payload["pause_request"]["engine_pause_supported"] is True
    assert saved["status"] == "approved"


def test_workflow_triggers_endpoint_returns_empty_state_for_new_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))

    with TestClient(create_app()) as client:
        response = client.get("/api/workflow_triggers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trigger_dir"] == str(tmp_path / "workflow_triggers")
    assert payload["count"] == 0
    assert payload["triggers"] == []
    assert payload["errors"] == []
    assert payload["scheduler_runner_contract_supported"] is True
    assert payload["durable_scheduler_supported"] is True
    assert payload["file_watch_runner_contract_supported"] is True
    assert payload["polling_file_watcher_supported"] is True
    assert payload["durable_trigger_runner_supported"] is True
    assert payload["run_submission_supported"] is False
    assert "pollable metadata" in payload["workflow_trigger_note"]
    assert "durable polling runner" in payload["workflow_trigger_note"]
    assert "submit embedded workflows" in payload["workflow_trigger_note"]


def test_workflow_triggers_endpoint_reports_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    malformed = trigger_dir / "schedule_broken.json"
    malformed.write_text("{not-json", encoding="utf-8")
    valid = trigger_dir / "schedule_weekly.json"
    valid.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"sample": "S1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/workflow_triggers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["triggers"][0]["trigger_file"] == str(valid)
    assert payload["triggers"][0]["target_workflow"] == "weekly-qc"
    assert payload["errors"] == [
        {
            "trigger_file": str(malformed),
            "error": f"workflow trigger file is not valid JSON: {malformed}",
        }
    ]


def test_workflow_triggers_endpoint_redacts_secret_payload_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    trigger_file = trigger_dir / "schedule_secret.json"
    trigger_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"api_key": "secret-key", "sample": "S1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/workflow_triggers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["triggers"][0]["payload"]["api_key"] == "***"
    assert payload["triggers"][0]["payload"]["sample"] == "S1"
    assert "secret-key" not in json.dumps(payload)


def test_workflow_trigger_evaluate_endpoint_lists_due_schedule(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    due_file = trigger_dir / "schedule_weekly.json"
    due_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"sample": "S1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        not_due = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:29:59+00:00"},
        )
        due = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:30:00+00:00"},
        )

    assert not_due.status_code == 200
    assert not_due.json()["due_schedule_count"] == 0
    assert due.status_code == 200
    payload = due.json()
    assert payload["due_schedule_count"] == 1
    assert payload["due_file_watch_count"] == 0
    assert payload["due_schedule_triggers"][0]["trigger_file"] == str(due_file)
    assert payload["due_schedule_triggers"][0]["target_workflow"] == "weekly-qc"
    assert payload["due_schedule_triggers"][0]["payload"] == {"sample": "S1"}
    assert payload["scheduler_runner_contract_supported"] is True
    assert payload["durable_scheduler_supported"] is True
    assert payload["file_watch_runner_contract_supported"] is True
    assert payload["polling_file_watcher_supported"] is True
    assert payload["durable_trigger_runner_supported"] is True
    assert payload["run_submission_supported"] is False
    assert "pollable metadata" in payload["workflow_trigger_note"]
    assert "durable polling runner" in payload["workflow_trigger_note"]
    assert "submit embedded workflows" in payload["workflow_trigger_note"]


def test_workflow_trigger_evaluate_redacts_secret_payload_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    due_file = trigger_dir / "schedule_secret.json"
    due_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"api_key": "secret-key", "sample": "S1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:30:00+00:00"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["due_schedule_triggers"][0]["payload"]["api_key"] == "***"
    assert payload["due_schedule_triggers"][0]["payload"]["sample"] == "S1"
    assert "secret-key" not in json.dumps(payload)


def test_workflow_trigger_evaluate_endpoint_submits_due_schedule_once_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    due_file = trigger_dir / "schedule_weekly.json"
    due_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"sample": "S1"},
                "workflow": {"name": "Weekly QC", "nodes": [], "edges": []},
            }
        ),
        encoding="utf-8",
    )

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs["run_id"])

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        queue = Queue()
        client.app.state.run_queue = queue
        first = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:30:00+00:00", "submit_runs": True},
        )
        second = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:30:00+00:00", "submit_runs": True},
        )

    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["run_submission_supported"] is True
    assert first_payload["submitted_run_count"] == 1
    assert first_payload["submitted_runs"][0]["trigger_file"] == str(due_file)
    assert first_payload["submitted_runs"][0]["status"] == "submitted"
    assert queue.submit_calls[0]["workflow"] == {"name": "Weekly QC", "nodes": [], "edges": []}
    assert queue.submit_calls[0]["options"] == {"parameters": {"sample": "S1"}}
    assert queue.submit_calls[0]["metadata"]["trigger_type"] == "schedule"
    assert queue.submit_calls[0]["metadata"]["target_workflow"] == "weekly-qc"

    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["submitted_run_count"] == 0
    assert second_payload["submitted_runs"][0]["status"] == "skipped"
    assert second_payload["submitted_runs"][0]["reason"] == "already_submitted"
    assert len(queue.submit_calls) == 1
    saved = json.loads(due_file.read_text(encoding="utf-8"))
    assert saved["last_submitted_due_at"] == "2026-06-07T18:30:00+00:00"
    assert saved["submitted_run_ids"] == [queue.submit_calls[0]["run_id"]]


def test_workflow_trigger_submission_redacts_secret_metadata_but_preserves_raw_queue_options(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    due_file = trigger_dir / "schedule_secret.json"
    due_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {
                    "api_key": "secret-key",
                    "sample": "S1",
                    "workflow": {"name": "Weekly QC", "nodes": [], "edges": []},
                },
            }
        ),
        encoding="utf-8",
    )

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs["run_id"])

        async def shutdown(self) -> None:
            return None

    with TestClient(create_app()) as client:
        queue = Queue()
        client.app.state.run_queue = queue
        response = client.post(
            "/api/workflow_triggers/evaluate",
            json={"now": "2026-06-07T18:30:00+00:00", "submit_runs": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert queue.submit_calls
    assert queue.submit_calls[0]["options"] == {"parameters": {"api_key": "secret-key", "sample": "S1"}}
    assert queue.submit_calls[0]["metadata"]["payload"]["api_key"] == "***"
    assert "secret-key" not in json.dumps(queue.submit_calls[0]["metadata"], default=str)
    assert "secret-key" not in json.dumps(payload)


def test_workflow_trigger_evaluate_endpoint_lists_file_watch_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    new_file = watch_dir / "new.fastq"
    new_file.write_text("@new\nTGCA\n+\n!!!!\n", encoding="utf-8")
    watch_file = trigger_dir / "file_watch_inbox.json"
    watch_file.write_text(
        json.dumps(
            {
                "trigger_type": "file_watch",
                "status": "registered",
                "target_workflow": "auto-import",
                "watch_path": str(watch_dir),
                "watch_event": "create",
                "baseline_snapshot": {},
                "payload": {"project": "P1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post("/api/workflow_triggers/evaluate", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["due_schedule_count"] == 0
    assert payload["due_file_watch_count"] == 1
    assert payload["due_file_watch_triggers"][0]["trigger_file"] == str(watch_file)
    assert payload["due_file_watch_triggers"][0]["target_workflow"] == "auto-import"
    assert payload["due_file_watch_triggers"][0]["payload"] == {"project": "P1"}
    assert payload["due_file_watch_triggers"][0]["events"] == [
        {
            "event": "create",
            "path": str(new_file),
            "relative_path": "new.fastq",
        }
    ]


def test_workflow_trigger_evaluate_advances_file_watch_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    new_file = watch_dir / "new.fastq"
    new_file.write_text("@new\nTGCA\n+\n!!!!\n", encoding="utf-8")
    watch_file = trigger_dir / "file_watch_inbox.json"
    watch_file.write_text(
        json.dumps(
            {
                "trigger_type": "file_watch",
                "status": "registered",
                "target_workflow": "auto-import",
                "watch_path": str(watch_dir),
                "watch_event": "create",
                "baseline_snapshot": {},
                "payload": {"project": "P1"},
            }
        ),
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        first_response = client.post("/api/workflow_triggers/evaluate", json={})
        second_response = client.post("/api/workflow_triggers/evaluate", json={})

    assert first_response.status_code == 200
    assert first_response.json()["due_file_watch_count"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["due_file_watch_count"] == 0

    saved = json.loads(watch_file.read_text(encoding="utf-8"))
    assert "new.fastq" in saved["baseline_snapshot"]

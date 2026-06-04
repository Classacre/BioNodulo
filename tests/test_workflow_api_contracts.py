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
    assert saved["status"] == "rejected"
    assert saved["approved"] is False

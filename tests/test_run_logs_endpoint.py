"""Contract tests for the run-logs endpoint hardening: path safety + paging."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _make_run(root, run_id: str, *, stdout_lines: int = 0, big_bytes: int = 0) -> None:
    run_dir = root / "runs" / run_id / "node_a"
    run_dir.mkdir(parents=True)
    meta = {
        "status": "completed",
        "started_at": "2026-06-16T00:00:00Z",
        "nodes": {"node_a": {"type": "fastqc", "status": "completed"}},
    }
    (root / "runs" / run_id / "run_metadata.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )
    if stdout_lines:
        (run_dir / "stdout.log").write_text(
            "\n".join(f"line-{i}" for i in range(stdout_lines)) + "\n",
            encoding="utf-8",
        )
    if big_bytes:
        (run_dir / "stderr.log").write_text("x" * big_bytes, encoding="utf-8")


def test_run_logs_rejects_path_traversal(monkeypatch, tmp_path) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        resp = client.get("/api/runs/..%2f..%2fetc/logs")
    # Either rejected as a bad run id (400) or simply not found — never a 200
    # that reads outside runs/.
    assert resp.status_code in (400, 404)


def test_run_logs_paginates(monkeypatch, tmp_path) -> None:
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    _make_run(tmp_path, "run_paged", stdout_lines=100)

    with TestClient(create_app()) as client:
        resp = client.get("/api/runs/run_paged/logs", params={"offset": 0, "limit": 10})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["logs"]) == 10
    assert body["total"] > 100  # 100 lines + synthetic engine/node events
    assert body["has_more"] is True
    assert body["limit"] == 10


def test_run_logs_caps_huge_file(monkeypatch, tmp_path) -> None:
    from bionodulo.api.routes import LOG_MAX_BYTES_PER_FILE
    from server import create_app

    monkeypatch.setenv("BIONODULO_ROOT", str(tmp_path))
    _make_run(tmp_path, "run_big", big_bytes=LOG_MAX_BYTES_PER_FILE * 2)

    with TestClient(create_app()) as client:
        resp = client.get("/api/runs/run_big/logs", params={"limit": 50000})

    assert resp.status_code == 200
    body = resp.json()
    assert "node_a/stderr.log" in body["truncated_files"]

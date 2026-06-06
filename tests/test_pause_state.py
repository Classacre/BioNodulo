from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from bionodulo.execution.pause_state import PauseStateStore


def test_pause_state_store_saves_loads_and_resolves_requests(tmp_path: Path) -> None:
    store = PauseStateStore(tmp_path / "pause_requests")

    pause_file = store.save(
        {
            "run_id": "run-1",
            "node_id": "pause-node",
            "status": "waiting",
            "approved": True,
            "message": "Review sample",
        }
    )

    assert pause_file == tmp_path / "pause_requests" / "run-1__pause-node.json"
    loaded = store.load(pause_file)
    assert loaded["status"] == "waiting"
    assert loaded["pause_file"] == str(pause_file)

    resolved = store.resolve(run_id="run-1", node_id="pause-node", action="approve", reviewer="ana", comment="QC reviewed")
    assert resolved["status"] == "approved"
    assert resolved["approved"] is True
    assert resolved["resolved_by"] == "ana"
    assert resolved["resolution_comment"] == "QC reviewed"
    assert resolved["review_decision_supported"] is True
    assert resolved["engine_pause_supported"] is True

    saved = json.loads(pause_file.read_text(encoding="utf-8"))
    assert saved["status"] == "approved"


def test_pause_state_store_cancels_requests_and_preserves_existing_metadata(tmp_path: Path) -> None:
    store = PauseStateStore(tmp_path / "pause_requests")
    pause_file = store.save({"run_id": "run-2", "node_id": "gate", "status": "waiting", "message": "Hold"})

    cancelled = store.cancel(pause_file)

    assert cancelled["status"] == "cancelled"
    assert cancelled["approved"] is False
    assert cancelled["message"] == "Hold"
    assert cancelled["pause_file"] == str(pause_file)
    assert cancelled["resolved_at"] <= time.time()


def test_pause_state_store_rejects_corrupt_or_missing_request_files(tmp_path: Path) -> None:
    store = PauseStateStore(tmp_path / "pause_requests")
    corrupt = tmp_path / "pause_requests" / "bad.json"
    corrupt.parent.mkdir()
    corrupt.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="pause request file is not valid JSON"):
        store.load(corrupt)

    with pytest.raises(FileNotFoundError, match="pause request was not found"):
        store.load_by_run_node("missing-run", "missing-node")


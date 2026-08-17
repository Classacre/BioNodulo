from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.queue import RunQueue
from bionodulo.execution.run_store import RunStore

CHECKPOINT_ENTRY = {
    "checkpoint_name": "after_qc",
    "checkpoint_path": "unused",
    "run_id": "orphan",
    "node_id": "qc",
    "node_type": "checkpoint",
}


class RecordingExecutor:
    def __init__(self, workspace_dir: Path, on_interrupt: str) -> None:
        self.calls: list[dict[str, Any]] = []
        self.workspace_dir = workspace_dir
        self.settings = SimpleNamespace(
            execution=SimpleNamespace(on_interrupt=on_interrupt)
        )

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"status": "completed"}


def _write_checkpoint_manifest(tmp_path: Path, run_id: str = "orphan") -> None:
    checkpoint_file = tmp_path / "checkpoints" / "after_qc.json"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_file.write_text('{"data":"qc-passed"}', encoding="utf-8")
    entry = dict(CHECKPOINT_ENTRY)
    entry["checkpoint_path"] = str(checkpoint_file)
    entry["run_id"] = run_id
    (tmp_path / "checkpoints" / "checkpoint_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0",
                "latest_by_run_node": {f"{run_id}:qc": entry},
            }
        ),
        encoding="utf-8",
    )
    return None


def _persist_run(store: RunStore, run_id: str, status: str) -> None:
    store.upsert(
        {
            "run_id": run_id,
            "status": status,
            "workflow": {"name": "recoverable", "nodes": [{"id": "qc", "type": "demo"}], "edges": []},
            "options": {"target_nodes": []},
            "metadata": {"name": "recoverable"},
            "force": False,
            "force_nodes": [],
        }
    )


@pytest.mark.asyncio
async def test_manual_mode_keeps_current_behaviour(tmp_path: Path) -> None:
    _write_checkpoint_manifest(tmp_path)
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "orphan", "running")
    _persist_run(store, "queued", "pending")

    executor = RecordingExecutor(tmp_path, on_interrupt="manual")
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    summary = queue.recover()

    assert summary["interrupted"] == ["orphan", "queued"] or set(summary["interrupted"]) == {
        "orphan",
        "queued",
    }
    assert summary.get("resumed", []) == []
    assert summary.get("requeued", []) == []
    assert queue._queue_items() == []
    assert executor.calls == []
    assert queue.get_run("orphan")["status"] == "interrupted"
    assert queue.get_run("queued")["status"] == "interrupted"
    await queue.shutdown()
    store.close()


@pytest.mark.asyncio
async def test_auto_resume_resubmits_checkointed_interrupted_run(tmp_path: Path) -> None:
    _write_checkpoint_manifest(tmp_path)
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "orphan", "running")

    executor = RecordingExecutor(tmp_path, on_interrupt="auto_resume")
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    summary = queue.recover()

    resumed_ids = summary.get("resumed", [])
    assert len(resumed_ids) == 1
    resume_id = resumed_ids[0]
    assert resume_id.startswith("orphan_resume_")

    # The resume is actually executed with the checkpoint attached.
    await asyncio.wait_for(queue._pending.join(), timeout=5.0)
    assert len(executor.calls) == 1
    options = executor.calls[0]["options"]
    assert options["resume_checkpoint"]["checkpoint_name"] == "after_qc"
    assert options["resume_checkpoint"]["run_id"] == "orphan"

    # Metadata tags recorded on the resumed run.
    resumed_run = store.get(resume_id)
    assert resumed_run["metadata"]["resumed_after_interrupt"] is True
    assert resumed_run["metadata"]["interrupted_run_id"] == "orphan"

    # The interrupted original stays in history, marked interrupted.
    assert queue.get_run("orphan")["status"] == "interrupted"
    await queue.shutdown()
    store.close()


@pytest.mark.asyncio
async def test_auto_resume_without_checkpoint_stays_manual(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "orphan", "running")

    executor = RecordingExecutor(tmp_path, on_interrupt="auto_resume")
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    summary = queue.recover()

    assert summary.get("resumed", []) == []
    assert queue._queue_items() == []
    assert executor.calls == []
    await queue.shutdown()
    store.close()


@pytest.mark.asyncio
async def test_auto_resume_reenqueues_pending_runs_under_original_id(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "never-started", "pending")

    executor = RecordingExecutor(tmp_path, on_interrupt="auto_resume")
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    summary = queue.recover()

    assert summary.get("requeued", []) == ["never-started"]
    await asyncio.wait_for(queue._pending.join(), timeout=5.0)
    assert len(executor.calls) == 1
    assert executor.calls[0]["run_id"] == "never-started"
    assert store.get("never-started")["status"] in ("running", "completed")
    await queue.shutdown()
    store.close()


@pytest.mark.asyncio
async def test_manual_mode_does_not_reenqueue_pending(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "never-started", "pending")

    executor = RecordingExecutor(tmp_path, on_interrupt="manual")
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    queue.recover()

    assert queue._queue_items() == []
    assert executor.calls == []
    assert queue.get_run("never-started")["status"] == "interrupted"
    await queue.shutdown()
    store.close()


def test_recovered_pending_request_is_fresh_not_history_duplicate(tmp_path: Path) -> None:
    _write_checkpoint_manifest(tmp_path)
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "pending-only", "pending")

    executor = RecordingExecutor(tmp_path, on_interrupt="auto_resume")

    async def _scenario() -> None:
        queue = RunQueue(executor=executor, max_concurrent=1, store=store)
        summary = queue.recover()
        pending_ids = [req.run_id for req in queue._queue_items()]
        history_ids = [req.run_id for req in queue._history]
        assert pending_ids == ["pending-only"]
        assert "pending-only" not in history_ids
        # No double submit: exactly one pending entry for the run.
        assert summary["requeued"] == ["pending-only"]
        assert summary["resumed"] == []
        await queue.shutdown()

    asyncio.run(_scenario())
    store.close()


def test_on_interrupt_env_override_follows_nested_convention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bionodulo.core.config import Settings

    assert Settings.from_env().execution.on_interrupt == "manual"
    monkeypatch.setenv("BIONODULO_EXECUTION__ON_INTERRUPT", "auto_resume")
    assert Settings.from_env().execution.on_interrupt == "auto_resume"


def test_queue_reads_policy_from_executor_settings(tmp_path: Path) -> None:
    _write_checkpoint_manifest(tmp_path)
    store = RunStore(tmp_path / "runs.db")
    _persist_run(store, "orphan", "running")
    executor = RecordingExecutor(tmp_path, on_interrupt="auto_resume")
    queue = RunQueue(executor=executor, store=store)

    assert queue._on_interrupt_policy() == "auto_resume"

    executor.settings.execution.on_interrupt = "manual"
    assert queue._on_interrupt_policy() == "manual"
    store.close()

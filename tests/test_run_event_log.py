from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.errors import NodeMemoryError
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.execution.run_store import RUN_EVENT_RETENTION, RunStore


class FlakyMemoryNode:
    RETURN_NAMES = ("default",)
    fail_times = 1
    calls = 0

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        FlakyMemoryNode.calls += 1
        if FlakyMemoryNode.calls <= FlakyMemoryNode.fail_times:
            raise NodeMemoryError("std::bad_alloc")
        return {"outputs": {"default": str(context.node_dir / "out.txt")}}


class PolicyNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        context.run_metadata.setdefault("retry_policies", []).append(
            {
                "node_id": "policy",
                "max_retries": 2,
                "retry_on": "memory",
                "delay_seconds": 0.0,
            }
        )
        return {"outputs": {"default": str(context.node_dir / "policy.txt")}}


class BlockerNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        await context.cancel_event.wait()
        from bionodulo.execution.subprocess_runner import CommandCancelledError

        raise CommandCancelledError("blocker")


class Registry:
    def get(self, node_type: str) -> Any:
        return {
            "flaky": FlakyMemoryNode,
            "blocker": BlockerNode,
            "policy": PolicyNode,
        }.get(node_type)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        execution=SimpleNamespace(
            max_workers=1,
            env_isolation="off",
            content_hashing="off",
            on_interrupt="manual",
        ),
        api_secrets={},
    )


def test_run_store_append_and_get_events_ordered(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")

    store.append_event("a", "queue_submit", {"status": "pending"})
    store.append_event("a", "queue_start", {"status": "running"})
    store.append_event("a", "queue_finish", {"status": "completed"})
    store.append_event("b", "queue_submit", {"status": "pending"})

    events = store.get_events("a")
    assert [event["type"] for event in events] == [
        "queue_submit",
        "queue_start",
        "queue_finish",
    ]
    assert [event["seq"] for event in events] == [1, 2, 3]
    assert events[0]["payload"] == {"status": "pending"}
    assert events[0]["ts"] > 0
    # Per-run sequences are independent.
    assert store.get_events("b")[0]["seq"] == 1
    assert store.event_count("a") == 3
    store.close()


def test_run_store_events_survive_close_and_reopen(tmp_path: Path) -> None:
    db_path = tmp_path / "runs.db"
    store = RunStore(db_path)
    store.append_event("run-1", "queue_submit", {"n": 1})
    store.close()

    reopened = RunStore(db_path)
    events = reopened.get_events("run-1")
    assert len(events) == 1
    assert events[0]["type"] == "queue_submit"
    assert events[0]["payload"] == {"n": 1}
    reopened.close()


def test_run_store_prunes_to_last_1000_events_per_run(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    for seq in range(RUN_EVENT_RETENTION + 5):
        store.append_event("busy", "tick", {"n": seq})

    events = store.get_events("busy", limit=RUN_EVENT_RETENTION + 100)
    assert len(events) == RUN_EVENT_RETENTION
    assert events[0]["seq"] == 6
    assert events[-1]["seq"] == RUN_EVENT_RETENTION + 5
    # Other runs are untouched.
    store.append_event("quiet", "tick", {"n": 0})
    assert store.event_count("quiet") == 1
    store.close()


def test_run_store_upgrades_existing_database_in_place(tmp_path: Path) -> None:
    import sqlite3

    db_path = tmp_path / "runs.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE runs (run_id TEXT PRIMARY KEY, status TEXT, workflow TEXT,"
        " options TEXT, metadata TEXT, force INTEGER, force_nodes TEXT, result TEXT,"
        " created_at REAL, started_at REAL, finished_at REAL, updated_at REAL)"
    )
    conn.execute(
        "INSERT INTO runs (run_id, status, workflow, options, metadata, force,"
        " force_nodes, updated_at) VALUES ('legacy', 'completed', '{}', '{}', '{}', 0, '[]', 0)"
    )
    conn.commit()
    conn.close()

    store = RunStore(db_path)
    store.append_event("legacy", "queue_submit", {"upgraded": True})
    assert store.get("legacy")["status"] == "completed"
    assert store.get_events("legacy")[0]["payload"] == {"upgraded": True}
    store.close()


@pytest.mark.asyncio
async def test_queue_persists_retry_and_typed_error_events(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    assert executor.run_store is store

    def _workflow() -> dict[str, Any]:
        return {
            "name": "retry-flow",
            "nodes": [
                {"id": "policy", "type": "policy"},
                {"id": "flaky", "type": "flaky"},
            ],
            "edges": [
                {
                    "from": {"node": "policy", "output": "default"},
                    "to": {"node": "flaky", "input": "input"},
                },
            ],
        }

    try:
        # Retry path: OOM once, then succeed -> node_retry is persisted.
        FlakyMemoryNode.calls = 0
        FlakyMemoryNode.fail_times = 1
        await queue.submit(_workflow(), run_id="run-retry")
        await asyncio.wait_for(queue._pending.join(), timeout=5.0)

        # Failure path: OOM every attempt -> node_error carries taxonomy code.
        # force=True so the node cache (primed by the successful retry run for
        # an identical graph) cannot swallow the failing execution.
        FlakyMemoryNode.calls = 0
        FlakyMemoryNode.fail_times = 99
        await queue.submit(_workflow(), run_id="run-fail", force=True)
        await asyncio.wait_for(queue._pending.join(), timeout=5.0)
    finally:
        # Shutdown closes the queue's store handle; reads below reopen the db
        # to prove the events are durable, not in-memory.
        await queue.shutdown()

    reopened = RunStore(tmp_path / "runs.db")
    retry_events = reopened.get_events("run-retry")
    retry_types = [event["type"] for event in retry_events]
    assert retry_types[0] == "queue_submit"
    assert "queue_start" in retry_types
    assert "node_retry" in retry_types
    assert retry_types[-1] == "queue_finish"
    seqs = [event["seq"] for event in retry_events]
    assert seqs == sorted(seqs)

    fail_events = reopened.get_events("run-fail")
    error_events = [event for event in fail_events if event["type"] == "node_error"]
    assert error_events
    assert error_events[0]["payload"]["error_code"] == "node_memory"
    reopened.close()


@pytest.mark.asyncio
async def test_run_dict_surfaces_event_count(tmp_path: Path) -> None:
    FlakyMemoryNode.calls = 0
    FlakyMemoryNode.fail_times = 0
    store = RunStore(tmp_path / "runs.db")
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    queue = RunQueue(executor=executor, max_concurrent=1, store=store)
    try:
        await queue.submit(
            {"name": "counted", "nodes": [{"id": "flaky", "type": "flaky"}], "edges": []},
            run_id="run-count",
        )
        await asyncio.wait_for(queue._pending.join(), timeout=5.0)

        entry = queue.get_run("run-count")
        assert entry is not None
        assert entry["event_count"] >= 3  # submit + start + finish
        assert queue.get_run_events("run-count")[0]["type"] == "queue_submit"
    finally:
        await queue.shutdown()
    store.close()

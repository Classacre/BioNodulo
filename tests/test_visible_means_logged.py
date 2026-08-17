"""Regression: visible-means-logged.

Everything the API / run dict surfaces about a run — per-node statuses and the
run-event stream — must be reconstructable from the RunStore alone after a
close/reopen plus recover(), for a successful run and a cancelled one.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.execution.run_store import RunStore
from bionodulo.execution.subprocess_runner import CommandCancelledError


class FastNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        return {"outputs": {"default": str(context.node_dir / "out.txt")}}


class BlockerNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        await context.cancel_event.wait()
        raise CommandCancelledError("blocker")


class Registry:
    def get(self, node_type: str) -> Any:
        return {"fast": FastNode, "blocker": BlockerNode}.get(node_type)


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


@pytest.mark.asyncio
async def test_statuses_and_events_reconstructable_from_store(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs.db")
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
        run_store=store,
    )
    streamed: list[tuple[str, str, dict[str, Any]]] = []

    def _record(event: str, data: dict[str, Any]) -> None:
        streamed.append((str(data.get("run_id", "")), event, data))

    queue = RunQueue(executor=executor, max_concurrent=1, emit=_record, store=store)

    async def _run_success() -> None:
        await queue.submit(
            {
                "name": "ok",
                "nodes": [
                    {"id": "a", "type": "fast"},
                    {"id": "b", "type": "fast"},
                ],
                "edges": [
                    {
                        "from": {"node": "a", "output": "default"},
                        "to": {"node": "b", "input": "input"},
                    },
                ],
            },
            run_id="ok-run",
        )
        await asyncio.wait_for(queue._pending.join(), timeout=5.0)

    async def _run_cancelled() -> None:
        await queue.submit(
            {
                "name": "cancel",
                "nodes": [
                    {"id": "blocker", "type": "blocker"},
                    {"id": "sibling", "type": "fast"},
                ],
                "edges": [],
            },
            run_id="cancel-run",
        )
        await asyncio.sleep(0.2)
        await queue.cancel("cancel-run")
        for _ in range(50):
            if "cancel-run" not in queue._running:
                break
            await asyncio.sleep(0.05)

    try:
        await _run_success()
        await _run_cancelled()
        # Read the live view while the store handle is still open (shutdown
        # below closes it); the reopened store must reproduce both views.
        ok_entry = queue.get_run("ok-run")
        cancel_entry = queue.get_run("cancel-run")
    finally:
        await queue.shutdown()

    assert ok_entry is not None and cancel_entry is not None
    ok_statuses = {entry["node_id"]: entry["status"] for entry in ok_entry["node_statuses"]}
    cancel_statuses = {entry["node_id"]: entry["status"] for entry in cancel_entry["node_statuses"]}
    assert ok_statuses == {"a": "completed", "b": "completed"}
    assert cancel_statuses["blocker"] == "cancelled"
    assert cancel_statuses["sibling"] == "skipped_cancelled"

    def _node_events(run_id: str) -> set[str]:
        return {
            event
            for rid, event, data in streamed
            if rid == run_id and event.startswith("node_")
        }

    streamed_ok = _node_events("ok-run")
    streamed_cancel = _node_events("cancel-run")
    assert "node_complete" in streamed_ok
    assert "node_skip" in streamed_cancel

    # ---- Simulate restart: close, reopen, recover, re-derive everything. ----
    store.close()
    reopened_store = RunStore(tmp_path / "runs.db")
    recovered_queue = RunQueue(
        executor=WorkflowExecutor(
            workspace_dir=tmp_path,
            cache_dir=tmp_path / "cache",
            registry=Registry(),
            settings=_settings(),
        ),
        store=reopened_store,
    )
    summary = recovered_queue.recover()
    assert summary["restored"] >= 2

    recovered_ok = recovered_queue.get_run("ok-run")
    recovered_cancel = recovered_queue.get_run("cancel-run")
    assert recovered_ok is not None and recovered_cancel is not None
    assert {entry["node_id"]: entry["status"] for entry in recovered_ok["node_statuses"]} == ok_statuses
    assert (
        {entry["node_id"]: entry["status"] for entry in recovered_cancel["node_statuses"]}
        == cancel_statuses
    )

    # Every per-node status visible in the stream has a terminal marker event
    # in the durable log, and queue lifecycle transitions are persisted.
    ok_events = reopened_store.get_events("ok-run")
    cancel_events = reopened_store.get_events("cancel-run")
    assert [event["type"] for event in ok_events][0] == "queue_submit"
    assert [event["type"] for event in ok_events][-1] == "queue_finish"
    persisted_cancel_types = {event["type"] for event in cancel_events}
    assert "node_skipped_cancelled" in persisted_cancel_types
    assert "queue_finish" in persisted_cancel_types
    assert reopened_store.event_count("ok-run") == ok_entry["event_count"]

    # Streams are ordered by sequence and timestamps are monotonic.
    for events in (ok_events, cancel_events):
        seqs = [event["seq"] for event in events]
        assert seqs == sorted(seqs)
        stamps = [event["ts"] for event in events]
        assert stamps == sorted(stamps)
    await recovered_queue.shutdown()
    reopened_store.close()

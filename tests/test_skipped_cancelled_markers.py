from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.execution.errors import NodeCancelledError
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.run_store import RunStore
from bionodulo.execution.subprocess_runner import CommandCancelledError


class BlockerNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        await context.cancel_event.wait()
        raise CommandCancelledError("blocker command")


class FastNode:
    RETURN_NAMES = ("default",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {"required": {}, "optional": {}, "hidden": {}}

    async def run(self, context: Any, **_: Any) -> dict[str, Any]:
        return {"outputs": {"default": str(context.node_dir / "out.txt")}}


class Registry:
    def get(self, node_type: str) -> Any:
        return {"blocker": BlockerNode, "fast": FastNode}.get(node_type)


def _settings(max_workers: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        execution=SimpleNamespace(
            max_workers=max_workers,
            env_isolation="off",
            content_hashing="off",
        ),
        api_secrets={},
    )


def _workflow() -> dict[str, Any]:
    return {
        "name": "cancel-markers",
        "nodes": [
            {"id": "blocker", "type": "blocker"},
            {"id": "sibling", "type": "fast"},
            {"id": "downstream", "type": "fast"},
        ],
        "edges": [
            {
                "from": {"node": "sibling", "output": "default"},
                "to": {"node": "downstream", "input": "input"},
            },
        ],
    }


@pytest.mark.asyncio
async def test_cancelled_run_marks_unstarted_nodes_skipped_cancelled(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    events: list[tuple[str, dict[str, Any]]] = []
    cancel_event = asyncio.Event()

    async def _cancel_soon() -> None:
        await asyncio.sleep(0.2)
        cancel_event.set()

    canceller = asyncio.create_task(_cancel_soon())
    try:
        result = await executor.execute(
            run_id="run-cancel",
            workflow=_workflow(),
            cancel_event=cancel_event,
            emit=lambda evt, data: events.append((evt, data)),
        )
    finally:
        await canceller

    assert result["status"] == "cancelled"
    # The in-flight node is "cancelled"; never-started nodes are marked.
    assert result["node_results"]["blocker"]["status"] == "cancelled"
    assert result["node_results"]["sibling"]["status"] == "skipped_cancelled"
    assert result["node_results"]["downstream"]["status"] == "skipped_cancelled"

    metadata_path = tmp_path / "runs" / "run-cancel" / "run_metadata.json"
    on_disk = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert on_disk["nodes"]["sibling"]["status"] == "skipped_cancelled"
    assert on_disk["nodes"]["downstream"]["status"] == "skipped_cancelled"

    skip_events = [
        data
        for evt, data in events
        if evt == "node_skip" and data.get("reason") == "skipped_cancelled"
    ]
    assert {entry["node_id"] for entry in skip_events} == {"sibling", "downstream"}


@pytest.mark.asyncio
async def test_cancelled_marker_is_distinct_from_inflight_cancelled(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    cancel_event = asyncio.Event()
    cancel_event.set()

    result = await executor.execute(
        run_id="run-pre-cancelled",
        workflow=_workflow(),
        cancel_event=cancel_event,
        emit=lambda *_: None,
    )

    assert result["status"] == "cancelled"
    statuses = {node_id: entry["status"] for node_id, entry in result["node_results"].items()}
    assert statuses == {
        "blocker": "skipped_cancelled",
        "sibling": "skipped_cancelled",
        "downstream": "skipped_cancelled",
    }


@pytest.mark.asyncio
async def test_completed_run_leaves_no_skipped_cancelled_markers(tmp_path: Path) -> None:
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
    )
    workflow = {
        "name": "all-fast",
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
    }

    result = await executor.execute(run_id="run-ok", workflow=workflow)

    assert result["status"] == "completed"
    assert all(
        entry["status"] != "skipped_cancelled" for entry in result["node_results"].values()
    )
    assert set(result["metadata"]["nodes"]) == {"a", "b"}


@pytest.mark.asyncio
async def test_skipped_cancelled_markers_persist_to_run_event_log(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "runs" / "runs.db")
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=Registry(),
        settings=_settings(),
        run_store=store,
    )
    cancel_event = asyncio.Event()

    async def _cancel_soon() -> None:
        await asyncio.sleep(0.2)
        cancel_event.set()

    canceller = asyncio.create_task(_cancel_soon())
    try:
        await executor.execute(
            run_id="run-events",
            workflow=_workflow(),
            cancel_event=cancel_event,
            emit=lambda *_: None,
        )
    finally:
        await canceller

    events = store.get_events("run-events")
    marked = [event for event in events if event["type"] == "node_skipped_cancelled"]
    assert {event["payload"]["node_id"] for event in marked} == {"sibling", "downstream"}
    store.close()


def test_node_cancelled_error_is_taxonomy_member() -> None:
    assert issubclass(CommandCancelledError, NodeCancelledError)

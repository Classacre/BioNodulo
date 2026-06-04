from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.api.app_state import AppState
from bionodulo.api.routes import _extract_workflow_subgraph
from bionodulo.api.schemas import RunCreateRequest, WorkflowExtractRequest
from bionodulo.execution.arq_executor import ArqWorkflowExecutor, maybe_wrap_with_arq
from bionodulo.execution.cache import CacheStore
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.queue import RunQueue
from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.manager.diagnostics import _check_r_packages_env_aware
from bionodulo.nodes.command_node import _shell_join
from bionodulo.workflow.graph import (
    edge_source,
    edge_source_port,
    edge_target,
    edge_target_port,
    topological_sort,
)


@pytest.mark.asyncio
async def test_run_subprocess_streams_to_log_files(tmp_path: Path) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"

    result = await run_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('streamed-out'); print('streamed-err', file=sys.stderr)",
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        emit=lambda event, data: events.append((event, data)),
    )

    assert result["returncode"] == 0
    assert "streamed-out" in result["stdout"]
    assert "streamed-err" in result["stderr"]
    assert stdout_path.read_text(encoding="utf-8").strip() == "streamed-out"
    assert stderr_path.read_text(encoding="utf-8").strip() == "streamed-err"
    assert ("log", {"node_id": "subprocess", "level": "stdout", "message": "streamed-out"}) in events


def test_cache_store_tracks_and_replaces_markers_atomically(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)

    store.write_marker("abc", outputs={"out": "one"})
    assert store.is_hit("abc")
    assert store.read_marker("abc")["outputs"] == {"out": "one"}

    store.write_marker("abc", outputs={"out": "two"})
    assert store.is_hit("abc")
    assert store.read_marker("abc")["outputs"] == {"out": "two"}


def test_shell_join_preserves_file_descriptor_redirects() -> None:
    command = _shell_join(["tool", "input file.txt", ">", "tool.log", "2>&1"])

    assert command == "tool 'input file.txt' > tool.log 2>&1"


def test_cache_clear_preserves_unrelated_files(tmp_path: Path) -> None:
    store = CacheStore(tmp_path)
    store.write_marker("abc", outputs={"out": "cached"})
    legacy_marker = tmp_path / "legacy.marker.json"
    legacy_marker.write_text("{}", encoding="utf-8")
    unrelated = tmp_path / "do-not-delete.txt"
    unrelated.write_text("keep me", encoding="utf-8")

    count = store.clear()

    assert count >= 1
    assert unrelated.read_text(encoding="utf-8") == "keep me"
    assert not legacy_marker.exists()
    assert not store.is_hit("abc")


def test_graph_helpers_support_frontend_and_legacy_edge_shapes() -> None:
    frontend_edge = {
        "from": {"node": "input", "output": "reads"},
        "to": {"node": "qc", "input": "reads"},
    }
    legacy_edge = {
        "source_node": "qc",
        "target_node": "multiqc",
        "source_output": "report",
        "target_input": "reports",
    }
    workflow = {
        "nodes": [{"id": "input"}, {"id": "qc"}, {"id": "multiqc"}],
        "edges": [frontend_edge, legacy_edge],
    }

    assert edge_source(frontend_edge) == "input"
    assert edge_source_port(frontend_edge) == "reads"
    assert edge_target(frontend_edge) == "qc"
    assert edge_target_port(frontend_edge) == "reads"
    assert edge_source(legacy_edge) == "qc"
    assert edge_target(legacy_edge) == "multiqc"
    assert topological_sort(workflow) == ["input", "qc", "multiqc"]


@pytest.mark.asyncio
async def test_run_queue_honors_max_concurrent() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.active = 0
            self.max_active = 0
            self.started = 0
            self.both_started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.started += 1
            if self.started == 2:
                self.both_started.set()
            await self.release.wait()
            self.active -= 1
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=2)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="one")
        await queue.submit({"nodes": [], "edges": []}, run_id="two")

        await asyncio.wait_for(executor.both_started.wait(), timeout=1.0)
        assert executor.max_active == 2

        executor.release.set()
        for _ in range(20):
            if len(queue.list_history()) == 2:
                break
            await asyncio.sleep(0.05)

        assert {entry["run_id"] for entry in queue.list_history()} == {"one", "two"}
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_releases_pending_join_accounting() -> None:
    class Executor:
        async def execute(self, **_: Any) -> dict[str, Any]:
            return {"status": "completed"}

    queue = RunQueue(executor=Executor(), max_concurrent=1)
    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="joinable")
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)
        assert queue.get_run("joinable")["status"] == "completed"
    finally:
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_reorders_pending_before_execution() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.started: list[str] = []
            self.first_started = asyncio.Event()
            self.release_first = asyncio.Event()

        async def execute(self, run_id: str, **_: Any) -> dict[str, Any]:
            self.started.append(run_id)
            if run_id == "one":
                self.first_started.set()
                await self.release_first.wait()
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="one")
        await asyncio.wait_for(executor.first_started.wait(), timeout=1.0)
        await queue.submit({"nodes": [], "edges": []}, run_id="two")
        await queue.submit({"nodes": [], "edges": []}, run_id="three")

        pending = await queue.reorder_pending("three", index=0)

        assert [entry["run_id"] for entry in pending] == ["three", "two"]

        executor.release_first.set()
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        assert executor.started == ["one", "three", "two"]
    finally:
        executor.release_first.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_cancel_pending_moves_run_to_history() -> None:
    class BlockingExecutor:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def execute(self, **_: Any) -> dict[str, Any]:
            self.started.set()
            await self.release.wait()
            return {"status": "completed"}

    executor = BlockingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit({"nodes": [], "edges": []}, run_id="running")
        await asyncio.wait_for(executor.started.wait(), timeout=1.0)
        await queue.submit({"nodes": [], "edges": []}, run_id="pending")

        assert await queue.cancel("pending") is True

        state = queue.queue_state()
        assert state["pending"] == []
        assert queue.get_run("pending")["status"] == "cancelled"
    finally:
        executor.release.set()
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_retry_uses_stored_workflow_options_and_force_nodes() -> None:
    class RecordingExecutor:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            self.calls.append(kwargs)
            return {"status": "completed"}

    workflow = {"name": "Retry Me", "nodes": [{"id": "a", "type": "demo"}], "edges": []}
    executor = RecordingExecutor()
    queue = RunQueue(executor=executor, max_concurrent=1)

    try:
        await queue.submit(
            workflow,
            run_id="original",
            options={"target_nodes": ["a"]},
            force_nodes={"a"},
            metadata={"name": "Retry Me"},
        )
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        await queue.retry("original", new_run_id="retry")
        await asyncio.wait_for(queue._pending.join(), timeout=1.0)

        assert len(executor.calls) == 2
        assert executor.calls[1]["workflow"] == workflow
        assert executor.calls[1]["options"] == {"target_nodes": ["a"]}
        assert executor.calls[1]["force_nodes"] == {"a"}
    finally:
        await queue.shutdown()


@pytest.mark.asyncio
async def test_run_queue_shutdown_closes_executor_cache() -> None:
    class Cache:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Executor:
        def __init__(self) -> None:
            self.cache = Cache()

    executor = Executor()
    queue = RunQueue(executor=executor)

    await queue.shutdown()

    assert executor.cache.closed


@pytest.mark.asyncio
async def test_workflow_executor_target_nodes_execute_upstream_dependencies_only(tmp_path: Path) -> None:
    class RecordingNode:
        RETURN_NAMES = ("out",)
        calls: list[str] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            self.calls.append(context.node_id)
            return {"outputs": {"out": context.node_id}}

    class Registry:
        def get(self, _node_type: str) -> type[RecordingNode]:
            return RecordingNode

    workflow = {
        "nodes": [
            {"id": "a", "type": "record", "outputs": {"out": {}}},
            {"id": "b", "type": "record", "outputs": {"out": {}}},
            {"id": "c", "type": "record", "outputs": {"out": {}}},
            {"id": "d", "type": "record", "outputs": {"out": {}}},
        ],
        "edges": [
            {"source_node": "a", "target_node": "b", "source_output": "out", "target_input": "in"},
            {"source_node": "b", "target_node": "c", "source_output": "out", "target_input": "in"},
            {"source_node": "a", "target_node": "d", "source_output": "out", "target_input": "in"},
        ],
    }
    RecordingNode.calls = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("targeted", workflow, options={"target_nodes": ["c"]})

    assert result["status"] == "completed"
    assert RecordingNode.calls == ["a", "b", "c"]
    assert set(result["outputs"]) == {"a", "b", "c"}
    assert result["metadata"]["target_nodes"] == ["c"]


@pytest.mark.asyncio
async def test_workflow_executor_context_exposes_executor_and_shared_run_metadata(tmp_path: Path) -> None:
    class ContextProbeNode:
        RETURN_NAMES = ("out",)
        observations: list[dict[str, Any]] = []

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            context.run_metadata.setdefault("context_probe", []).append(context.node_id)
            self.observations.append({
                "node_id": context.node_id,
                "has_executor": context.executor is not None,
                "shared_metadata": context.run_metadata,
            })
            return {"outputs": {"out": context.node_id}}

    class Registry:
        def get(self, _node_type: str) -> type[ContextProbeNode]:
            return ContextProbeNode

    workflow = {
        "nodes": [{"id": "probe", "type": "context_probe", "outputs": {"out": {}}}],
        "edges": [],
    }
    ContextProbeNode.observations = []
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    result = await executor.execute("context-run", workflow)

    assert result["status"] == "completed"
    assert result["metadata"]["context_probe"] == ["probe"]
    assert ContextProbeNode.observations == [{
        "node_id": "probe",
        "has_executor": True,
        "shared_metadata": result["metadata"],
    }]


@pytest.mark.asyncio
async def test_workflow_executor_always_run_cache_policy_bypasses_generic_cache(tmp_path: Path) -> None:
    class AlwaysRunNode:
        RETURN_NAMES = ("out",)
        EXECUTOR_CACHE_POLICY = "always_run"
        calls = 0

        @classmethod
        def INPUT_TYPES(cls) -> dict[str, Any]:
            return {}

        def run(self, context, **_: Any) -> dict[str, Any]:
            type(self).calls += 1
            return {"outputs": {"out": f"run-{type(self).calls}"}}

    class Registry:
        def get(self, _node_type: str) -> type[AlwaysRunNode]:
            return AlwaysRunNode

    workflow = {
        "nodes": [{"id": "control", "type": "always_run", "outputs": {"out": {}}}],
        "edges": [],
    }
    AlwaysRunNode.calls = 0
    executor = WorkflowExecutor(workspace_dir=tmp_path, cache_dir=tmp_path / "cache", registry=Registry())

    first = await executor.execute("first", workflow)
    second = await executor.execute("second", workflow)

    assert first["outputs"]["control"]["out"] == "run-1"
    assert second["outputs"]["control"]["out"] == "run-2"
    assert second["node_results"]["control"]["status"] == "completed"
    assert second["node_results"]["control"]["cache_key"] is None


def test_execution_request_schemas_accept_frontend_gap_fields() -> None:
    run_request = RunCreateRequest(
        workflow={"nodes": [], "edges": []},
        force_nodes=["qc"],
        target_nodes=["report"],
    )
    extract_request = WorkflowExtractRequest(
        workflow={"nodes": [{"id": "qc"}], "edges": []},
        node_ids=["qc"],
        name="QC only",
    )

    assert run_request.force_nodes == ["qc"]
    assert run_request.target_nodes == ["report"]
    assert extract_request.node_ids == ["qc"]


def test_workflow_subgraph_extraction_keeps_only_internal_references() -> None:
    workflow = {
        "id": "wf",
        "name": "Full",
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"source_node": "a", "target_node": "b"},
            {"source_node": "b", "target_node": "c"},
            {"source_node": "a", "target_node": "c"},
        ],
        "groups": [{"id": "g", "node_ids": ["a", "c"]}],
        "outputs": [
            {"name": "keep", "node_id": "b", "output_name": "out"},
            {"name": "drop", "node_id": "c", "output_name": "out"},
        ],
    }

    extracted = _extract_workflow_subgraph(workflow, ["a", "b"], "Sub")

    assert extracted["name"] == "Sub"
    assert [node["id"] for node in extracted["nodes"]] == ["a", "b"]
    assert extracted["edges"] == [{"source_node": "a", "target_node": "b"}]
    assert extracted["groups"] == [{"id": "g", "node_ids": ["a"]}]
    assert extracted["outputs"] == [{"name": "keep", "node_id": "b", "output_name": "out"}]


@pytest.mark.asyncio
async def test_sync_r_diagnostics_do_not_block_running_event_loop() -> None:
    result = _check_r_packages_env_aware(["DefinitelyMissingPackage"], {})
    assert result["DefinitelyMissingPackage"]["available"] is False


def test_dependency_installer_is_app_scoped() -> None:
    state_one = AppState(SimpleNamespace())
    state_two = AppState(SimpleNamespace())

    assert state_one.dependency_installer is state_one.dependency_installer
    assert state_one.dependency_installer is not state_two.dependency_installer


def test_arq_execution_backend_is_opt_in(monkeypatch) -> None:
    executor = SimpleNamespace(workspace_dir="workspace", cache=SimpleNamespace(cache_dir="cache"))

    monkeypatch.delenv("BIONODULO_EXECUTION_BACKEND", raising=False)
    assert maybe_wrap_with_arq(executor) is executor

    monkeypatch.setenv("BIONODULO_EXECUTION_BACKEND", "arq")
    wrapped = maybe_wrap_with_arq(executor)

    assert isinstance(wrapped, ArqWorkflowExecutor)
    assert str(wrapped.workspace_dir) == "workspace"
    assert str(wrapped.cache_dir) == "cache"

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.api.app_state import AppState
from bionodulo.execution.arq_executor import ArqWorkflowExecutor, maybe_wrap_with_arq
from bionodulo.execution.cache import CacheStore
from bionodulo.execution.queue import RunQueue
from bionodulo.execution.subprocess_runner import run_subprocess
from bionodulo.manager.diagnostics import _check_r_packages_env_aware
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

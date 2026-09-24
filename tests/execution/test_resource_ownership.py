from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import bionodulo.execution.arq_executor as arq_executor
import bionodulo.execution.hpc_job_runner as hpc_job_runner
from bionodulo.execution.executor import WorkflowExecutor


class _Cache:
    def __init__(self, cache_dir: Path, events: list[str]) -> None:
        self.cache_dir = cache_dir
        self.events = events
        self.closed = False

    def close(self) -> None:
        self.events.append("cache-close")
        self.closed = True


def test_arq_replacement_closes_local_cache_after_adapter_initializes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    cache = _Cache(tmp_path / "cache", events)
    executor = SimpleNamespace(workspace_dir=tmp_path / "workspace", cache=cache)
    wrapped = object()

    def create_adapter(**kwargs: Any) -> object:
        events.append("adapter-init")
        assert kwargs == {
            "workspace_dir": tmp_path / "workspace",
            "cache_dir": tmp_path / "cache",
        }
        assert not cache.closed
        return wrapped

    monkeypatch.setenv(arq_executor.ARQ_BACKEND_ENV, "arq")
    monkeypatch.setattr(arq_executor, "ArqWorkflowExecutor", create_adapter)

    result = arq_executor.maybe_wrap_with_arq(executor)

    assert result is wrapped
    assert cache.closed
    assert events == ["adapter-init", "cache-close"]


def test_arq_initialization_failure_retains_local_cache_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    cache = _Cache(tmp_path / "cache", events)
    executor = SimpleNamespace(workspace_dir=tmp_path / "workspace", cache=cache)

    def fail_adapter(**_kwargs: Any) -> object:
        events.append("adapter-init")
        raise RuntimeError("adapter failed")

    monkeypatch.setenv(arq_executor.ARQ_BACKEND_ENV, "arq")
    monkeypatch.setattr(arq_executor, "ArqWorkflowExecutor", fail_adapter)

    with pytest.raises(RuntimeError, match="adapter failed"):
        arq_executor.maybe_wrap_with_arq(executor)

    assert not cache.closed
    assert events == ["adapter-init"]


def test_arq_replacement_closes_actual_local_sqlite_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ownership transfer closes the real diskcache SQLite handle.

    This covers adapter construction and cache ownership only; the lazy ARQ
    adapter does not connect to Redis until execution begins.
    """
    executor = WorkflowExecutor(
        workspace_dir=tmp_path / "workspace",
        cache_dir=tmp_path / "cache",
    )
    connection = executor.cache._metadata._local.con
    assert connection.execute("SELECT 1").fetchone() == (1,)
    monkeypatch.setenv(arq_executor.ARQ_BACKEND_ENV, "arq")

    try:
        wrapped = arq_executor.maybe_wrap_with_arq(executor)

        assert isinstance(wrapped, arq_executor.ArqWorkflowExecutor)
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")
    finally:
        # Safe if the ownership transfer already closed it, and guarantees
        # cleanup if construction or an assertion above fails.
        executor.cache.close()


@pytest.mark.asyncio
async def test_hpc_runner_closes_cache_after_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    cache = _Cache(tmp_path / "workspace" / "cache", events)

    class Registry:
        def load_builtin_nodes(self) -> None:
            events.append("registry-load")

    class Executor:
        def __init__(self, **kwargs: Any) -> None:
            events.append("executor-init")
            assert kwargs["cache_dir"] == tmp_path / "workspace" / "cache"
            self.cache = cache

        async def execute(self, **kwargs: Any) -> dict[str, Any]:
            events.append("execute")
            assert kwargs["run_id"] == "run-1"
            return {"status": "completed"}

    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    monkeypatch.setattr(
        hpc_job_runner,
        "NodeRegistry",
        SimpleNamespace(create_isolated=lambda: Registry()),
    )
    monkeypatch.setattr(hpc_job_runner, "WorkflowExecutor", Executor)

    result = await hpc_job_runner._execute(
        SimpleNamespace(
            workflow=str(workflow_path),
            workspace=str(tmp_path / "workspace"),
            run_id="run-1",
        )
    )

    assert result == {"status": "completed"}
    assert cache.closed
    assert events == ["registry-load", "executor-init", "execute", "cache-close"]


@pytest.mark.asyncio
async def test_hpc_runner_closes_cache_and_preserves_execution_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    cache = _Cache(tmp_path / "workspace" / "cache", events)

    class Registry:
        def load_builtin_nodes(self) -> None:
            events.append("registry-load")

    class Executor:
        def __init__(self, **_kwargs: Any) -> None:
            events.append("executor-init")
            self.cache = cache

        async def execute(self, **_kwargs: Any) -> dict[str, Any]:
            events.append("execute")
            raise RuntimeError("workflow failed")

    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text('{"nodes": [], "edges": []}', encoding="utf-8")
    monkeypatch.setattr(
        hpc_job_runner,
        "NodeRegistry",
        SimpleNamespace(create_isolated=lambda: Registry()),
    )
    monkeypatch.setattr(hpc_job_runner, "WorkflowExecutor", Executor)

    with pytest.raises(RuntimeError, match="workflow failed"):
        await hpc_job_runner._execute(
            SimpleNamespace(
                workflow=str(workflow_path),
                workspace=str(tmp_path / "workspace"),
                run_id="run-fail",
            )
        )

    assert cache.closed
    assert events == ["registry-load", "executor-init", "execute", "cache-close"]

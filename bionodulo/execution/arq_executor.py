"""Optional ARQ-backed workflow execution.

The public API stays compatible with ``WorkflowExecutor.execute`` so the
existing RunQueue, REST routes, and UI state can keep using one facade while
deployments with Redis can move execution work into ARQ workers.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Callable

from bionodulo.core.config import Settings
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.registry import NodeRegistry

ARQ_BACKEND_ENV = "BIONODULO_EXECUTION_BACKEND"
ARQ_REDIS_ENV = "BIONODULO_ARQ_REDIS_URL"


def _redis_dsn() -> str:
    return (
        os.environ.get(ARQ_REDIS_ENV)
        or os.environ.get("BIONODULO_REDIS_URL")
        or "redis://localhost:6379/0"
    )


def _load_worker_executor(workspace_dir: str | None, cache_dir: str | None) -> WorkflowExecutor:
    settings = Settings.from_env()
    registry = NodeRegistry()
    registry.load_builtin_nodes()
    registry.load_custom_nodes(settings.custom_nodes_dir)
    return WorkflowExecutor(
        workspace_dir=Path(workspace_dir) if workspace_dir else settings.project_root,
        cache_dir=Path(cache_dir) if cache_dir else settings.cache_dir,
        registry=registry,
        settings=settings,
    )


async def execute_workflow_job(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """ARQ worker entrypoint for one workflow run."""
    del ctx
    executor = _load_worker_executor(payload.get("workspace_dir"), payload.get("cache_dir"))
    try:
        return await executor.execute(
            run_id=str(payload["run_id"]),
            workflow=payload["workflow"],
            force=bool(payload.get("force", False)),
            force_nodes=set(payload.get("force_nodes", [])),
            options=dict(payload.get("options") or {}),
        )
    finally:
        cache = getattr(executor, "cache", None)
        close = getattr(cache, "close", None)
        if callable(close):
            close()


class ArqWorkflowExecutor:
    """WorkflowExecutor-compatible adapter that dispatches jobs to ARQ."""

    def __init__(
        self,
        workspace_dir: str | Path | None = None,
        cache_dir: str | Path | None = None,
        redis_dsn: str | None = None,
    ) -> None:
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.redis_dsn = redis_dsn or _redis_dsn()
        self._pool: Any = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self) -> Any:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                from arq.connections import RedisSettings, create_pool

                self._pool = await create_pool(RedisSettings.from_dsn(self.redis_dsn))
        return self._pool

    async def execute(
        self,
        run_id: str,
        workflow: dict[str, Any],
        record: Any | None = None,
        force: bool = False,
        force_nodes: set[str] | None = None,
        options: dict[str, Any] | None = None,
        cancel_event: asyncio.Event | None = None,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        del record
        if emit is not None:
            emit("execution_backend", {"backend": "arq", "run_id": run_id})
        pool = await self._get_pool()
        payload = {
            "run_id": run_id,
            "workflow": workflow,
            "force": force,
            "force_nodes": sorted(force_nodes or set()),
            "options": options or {},
            "workspace_dir": str(self.workspace_dir) if self.workspace_dir else None,
            "cache_dir": str(self.cache_dir) if self.cache_dir else None,
        }
        job = await pool.enqueue_job("execute_workflow_job", payload, _job_id=run_id)
        if job is None:
            # A job with this id already exists (e.g. resubmit after a restart
            # where Redis still holds it). Attach to it and await its result
            # instead of hard-failing.
            from arq.jobs import Job

            job = Job(run_id, pool)

        cancel_event = cancel_event or asyncio.Event()
        while True:
            if cancel_event.is_set():
                await job.abort(timeout=5)
                return {"status": "cancelled", "run_id": run_id}
            try:
                return await job.result(timeout=0.5)
            except asyncio.TimeoutError:
                continue

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose(close_connection_pool=True)
            self._pool = None


def maybe_wrap_with_arq(executor: WorkflowExecutor) -> WorkflowExecutor | ArqWorkflowExecutor:
    """Wrap the local executor when ARQ execution is explicitly enabled."""
    if os.environ.get(ARQ_BACKEND_ENV, "local").lower() != "arq":
        return executor
    cache = getattr(executor, "cache", None)
    return ArqWorkflowExecutor(
        workspace_dir=getattr(executor, "workspace_dir", None),
        cache_dir=getattr(cache, "cache_dir", None),
    )


class WorkerSettings:
    functions = [execute_workflow_job]
    try:
        from arq.connections import RedisSettings

        redis_settings = RedisSettings.from_dsn(_redis_dsn())
    except Exception:
        redis_settings = None
    allow_abort_jobs = True
    max_jobs = int(os.environ.get("BIONODULO_ARQ_MAX_JOBS", "4"))

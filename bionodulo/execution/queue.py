"""
RunQueue - async queue for workflow execution.

Manages pending, running, and completed workflow runs with support for
interruption, clearing, and state broadcast.
"""

from __future__ import annotations

import asyncio
import copy
import inspect
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.arq_executor import maybe_wrap_with_arq


class RunStatus(str, Enum):
    """Status of a workflow run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass
class RunRequest:
    """A request to execute a workflow."""

    run_id: str
    workflow: dict[str, Any]
    options: dict[str, Any] = field(default_factory=dict)
    force: bool = False
    force_nodes: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    status: RunStatus = RunStatus.PENDING
    result: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class RunQueue:
    """Async queue for managing workflow execution runs.

    Uses a single worker asyncio task to process runs sequentially
    (or with configurable concurrency).
    """

    def __init__(
        self,
        executor: WorkflowExecutor | None = None,
        max_concurrent: int = 0,
        emit: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.executor = maybe_wrap_with_arq(executor or WorkflowExecutor())
        self.max_concurrent = max_concurrent if max_concurrent > 0 else min(4, os.cpu_count() or 1)
        self.emit = emit or (lambda _evt, _data: None)

        self._pending: asyncio.Queue[RunRequest] = asyncio.Queue()
        self._pending_items: list[RunRequest] = []
        self._running: dict[str, RunRequest] = {}
        self._history: list[RunRequest] = []
        self._worker_task: asyncio.Task[None] | None = None
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._worker_start_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(
        self,
        workflow: dict[str, Any],
        run_id: str | None = None,
        options: dict[str, Any] | None = None,
        force: bool = False,
        force_nodes: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Submit a workflow to the execution queue.

        Returns:
            The assigned ``run_id``.
        """
        rid = run_id or f"run_{uuid.uuid4().hex[:12]}"
        request = RunRequest(
            run_id=rid,
            workflow=workflow,
            options=options or {},
            force=force,
            force_nodes=force_nodes or set(),
            metadata=metadata or {},
        )
        async with self._lock:
            self._pending_items.append(request)
        await self._pending.put(request)
        self.emit("queue_submit", {"run_id": rid, "status": "pending"})
        await self._emit_queue()

        await self._ensure_worker()

        return rid

    async def interrupt(self, run_id: str | None = None) -> bool:
        """Interrupt a running or pending run.

        If *run_id* is *None*, interrupts the currently running run.
        If the run is pending, it is removed from the queue.

        Returns:
            *True* if a run was interrupted.
        """
        if run_id and run_id in self._running:
            self._running[run_id].cancel_event.set()
            self._running[run_id].status = RunStatus.INTERRUPTED
            self.emit("queue_interrupt", {"run_id": run_id})
            await self._emit_queue()
            return True

        if not run_id and self._running:
            rid, req = next(iter(self._running.items()))
            req.cancel_event.set()
            req.status = RunStatus.INTERRUPTED
            self.emit("queue_interrupt", {"run_id": rid})
            await self._emit_queue()
            return True

        if run_id:
            removed = False
            async with self._lock:
                for req in list(self._pending_items):
                    if req.run_id != run_id:
                        continue
                    self._pending_items.remove(req)
                    req.status = RunStatus.INTERRUPTED
                    req.finished_at = time.time()
                    self._history.append(req)
                    removed = True
                    self.emit("queue_interrupt", {"run_id": run_id})
                    break
            if removed:
                await self._emit_queue()
                return True

        return False

    async def cancel(self, run_id: str | None = None) -> bool:
        """Cancel a running or pending run.

        If *run_id* is *None*, cancels the first currently running run.
        Pending runs are removed from the visible queue and moved to history.

        Returns:
            *True* if a run was cancelled.
        """
        if run_id and run_id in self._running:
            self._running[run_id].cancel_event.set()
            self._running[run_id].status = RunStatus.CANCELLED
            self.emit("queue_cancel", {"run_id": run_id})
            await self._emit_queue()
            return True

        if not run_id and self._running:
            rid, req = next(iter(self._running.items()))
            req.cancel_event.set()
            req.status = RunStatus.CANCELLED
            self.emit("queue_cancel", {"run_id": rid})
            await self._emit_queue()
            return True

        if run_id:
            removed = False
            async with self._lock:
                for req in list(self._pending_items):
                    if req.run_id != run_id:
                        continue
                    self._pending_items.remove(req)
                    req.cancel_event.set()
                    req.status = RunStatus.CANCELLED
                    req.finished_at = time.time()
                    self._history.append(req)
                    removed = True
                    self.emit("queue_cancel", {"run_id": run_id})
                    break
            if removed:
                await self._emit_queue()
                return True

        return False

    async def clear_pending(self) -> int:
        """Clear all pending runs from the queue.

        Returns:
            Number of cleared runs.
        """
        async with self._lock:
            pending = list(self._pending_items)
            self._pending_items.clear()
            for req in pending:
                req.cancel_event.set()
                req.status = RunStatus.CANCELLED
                req.finished_at = time.time()
                self._history.append(req)
        count = len(pending)
        self.emit("queue_clear", {"cleared": count})
        await self._emit_queue()
        return count

    async def clear(self) -> int:
        """Compatibility alias for clearing all pending runs."""
        return await self.clear_pending()

    async def reorder_pending(
        self,
        run_id: str,
        index: int | None = None,
        before_run_id: str | None = None,
        after_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Move a pending run to a new position.

        Exactly one destination may be supplied: ``index``, ``before_run_id``,
        or ``after_run_id``. Returns the updated pending queue snapshot.
        """
        destinations = [index is not None, before_run_id is not None, after_run_id is not None]
        if sum(destinations) != 1:
            raise ValueError("Specify exactly one of index, before_run_id, or after_run_id")

        async with self._lock:
            pending = self._pending_items
            current_index = next((idx for idx, req in enumerate(pending) if req.run_id == run_id), None)
            if current_index is None:
                raise KeyError(f"Pending run '{run_id}' not found")

            request = pending.pop(current_index)

            if before_run_id is not None:
                if before_run_id == run_id:
                    target_index = current_index
                else:
                    target_index = next(
                        (idx for idx, req in enumerate(pending) if req.run_id == before_run_id),
                        None,
                    )
                    if target_index is None:
                        pending.insert(current_index, request)
                        raise KeyError(f"Pending run '{before_run_id}' not found")
            elif after_run_id is not None:
                if after_run_id == run_id:
                    target_index = current_index
                else:
                    anchor_index = next(
                        (idx for idx, req in enumerate(pending) if req.run_id == after_run_id),
                        None,
                    )
                    if anchor_index is None:
                        pending.insert(current_index, request)
                        raise KeyError(f"Pending run '{after_run_id}' not found")
                    target_index = anchor_index + 1
            else:
                target_index = min(index or 0, len(pending))

            pending.insert(target_index, request)
            snapshot = [self._run_to_dict(req, include_result=False) for req in pending]

        self.emit(
            "queue_reorder",
            {"run_id": run_id, "pending": [entry["run_id"] for entry in snapshot]},
        )
        await self._emit_queue()
        return snapshot

    async def retry(self, run_id: str, new_run_id: str | None = None) -> str:
        """Submit a new run using the stored workflow from an existing run."""
        async with self._lock:
            original = self._find_request_locked(run_id)
            if original is None:
                raise KeyError(f"Run '{run_id}' not found")

            try:
                workflow = copy.deepcopy(original.workflow)
            except Exception:
                workflow = dict(original.workflow)
            options = copy.deepcopy(original.options)
            metadata = copy.deepcopy(original.metadata)
            force_nodes = set(original.force_nodes)
            force = original.force

        metadata["retry_of"] = run_id
        metadata.setdefault("name", f"{run_id} retry")
        rid = new_run_id or f"{run_id}_retry_{uuid.uuid4().hex[:6]}"
        return await self.submit(
            workflow=workflow,
            run_id=rid,
            options=options,
            force=force,
            force_nodes=force_nodes,
            metadata=metadata,
        )

    def _run_to_dict(self, r: RunRequest, include_result: bool = True) -> dict[str, Any]:
        """Serialize a RunRequest to a dict with optional result fields."""
        entry: dict[str, Any] = {
            "run_id": r.run_id,
            "status": r.status.value,
            "workflow_name": r.metadata.get("name", "Untitled"),
            "created_at": r.created_at,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
        }
        if include_result and r.result:
            entry["previews"] = {
                p.get("node_id", ""): p.get("path", "")
                for p in r.result.get("previews", [])
                if p.get("node_id")
            }
            entry["artifacts"] = {
                a.get("node_id", ""): a.get("path", "")
                for a in r.result.get("artifacts", [])
                if a.get("node_id")
            }
            meta = r.result.get("metadata", {})
            if meta.get("nodes"):
                entry["node_statuses"] = [
                    {"node_id": nid, "status": ninfo.get("status", "unknown")}
                    for nid, ninfo in meta["nodes"].items()
                ]
        return entry

    def queue_state(self) -> dict[str, Any]:
        """Get the current queue state."""
        return {
            "pending": [self._run_to_dict(r, include_result=False) for r in self._queue_items()],
            "running": [self._run_to_dict(r, include_result=True) for r in self._running.values()],
            "max_concurrent": self.max_concurrent,
        }

    async def get_state(self) -> dict[str, Any]:
        """Async wrapper for queue_state."""
        return self.queue_state()

    def list_runs(self) -> list[dict[str, Any]]:
        """List all runs (pending + running)."""
        runs: list[dict[str, Any]] = []
        for r in self._queue_items():
            runs.append(self._run_to_dict(r, include_result=False))
        for r in self._running.values():
            runs.append(self._run_to_dict(r, include_result=True))
        return runs

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a specific run by ID."""
        for r in self._queue_items():
            if r.run_id == run_id:
                return {
                    "run_id": r.run_id,
                    "status": r.status.value,
                    "workflow_name": r.metadata.get("name", "Untitled"),
                    "created_at": r.created_at,
                    "result": r.result,
                }
        if run_id in self._running:
            r = self._running[run_id]
            return {
                "run_id": r.run_id,
                "status": r.status.value,
                "workflow_name": r.metadata.get("name", "Untitled"),
                "created_at": r.created_at,
                "started_at": r.started_at,
                "result": r.result,
            }
        for r in self._history:
            if r.run_id == run_id:
                return {
                    "run_id": r.run_id,
                    "status": r.status.value,
                    "workflow_name": r.metadata.get("name", "Untitled"),
                    "created_at": r.created_at,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                    "result": r.result,
                }
        return None

    def list_history(self) -> list[dict[str, Any]]:
        """List completed (historic) runs."""
        history = []
        for r in reversed(self._history):
            entry: dict[str, Any] = {
                "run_id": r.run_id,
                "status": r.status.value,
                "workflow_name": r.metadata.get("name", "Untitled"),
                "created_at": r.created_at,
                "started_at": r.started_at,
                "finished_at": r.finished_at,
            }
            if r.result:
                # Extract previews as a node_id -> path mapping
                previews: dict[str, str] = {}
                for p in r.result.get("previews", []):
                    nid = p.get("node_id", "")
                    if nid:
                        previews[nid] = p.get("path", "")
                if previews:
                    entry["previews"] = previews
                # Extract artifacts as a node_id -> path mapping
                artifacts: dict[str, str] = {}
                for a in r.result.get("artifacts", []):
                    nid = a.get("node_id", "")
                    if nid:
                        artifacts[nid] = a.get("path", "")
                if artifacts:
                    entry["artifacts"] = artifacts
            history.append(entry)
        return history

    async def shutdown(self) -> None:
        """Gracefully shut down the queue worker."""
        self._shutdown_event.set()
        for req in self._running.values():
            req.cancel_event.set()
        for task in tuple(self._active_tasks):
            task.cancel()
        if self._worker_task and not self._worker_task.done():
            try:
                await asyncio.wait_for(self._worker_task, timeout=10.0)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass
        cache = getattr(self.executor, "cache", None)
        close = getattr(cache, "close", None)
        if callable(close):
            close()
        executor_close = getattr(self.executor, "close", None)
        if callable(executor_close):
            maybe_close = executor_close()
            if inspect.isawaitable(maybe_close):
                await maybe_close

    # ------------------------------------------------------------------
    # Worker
    # ------------------------------------------------------------------

    async def _worker(self) -> None:
        """Async scheduler that keeps up to ``max_concurrent`` runs active."""
        while not self._shutdown_event.is_set():
            if len(self._active_tasks) >= self.max_concurrent:
                await asyncio.wait(self._active_tasks, return_when=asyncio.FIRST_COMPLETED)
                continue

            try:
                await asyncio.wait_for(
                    self._pending.get(), timeout=0.5
                )
            except asyncio.TimeoutError:
                continue

            async with self._lock:
                if not self._pending_items:
                    self._pending.task_done()
                    continue
                request = self._pending_items.pop(0)
                if request.status is not RunStatus.PENDING:
                    self._pending.task_done()
                    continue

            task = asyncio.create_task(self._run_and_mark_done(request))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    async def _run_and_mark_done(self, request: RunRequest) -> None:
        """Run one request and release the pending queue accounting."""
        try:
            await self._run_request(request)
        finally:
            self._pending.task_done()

    async def _run_request(self, request: RunRequest) -> None:
        """Execute one queued request and update queue state."""
        async with self._lock:
            self._running[request.run_id] = request
            request.status = RunStatus.RUNNING
            request.started_at = time.time()

        self.emit("queue_start", {"run_id": request.run_id})
        await self._emit_queue()

        try:
            def _emit_wrapper(event: str, data: dict[str, Any]) -> None:
                data["run_id"] = request.run_id
                self.emit(event, data)

            result = await self.executor.execute(
                run_id=request.run_id,
                workflow=request.workflow,
                force=request.force,
                force_nodes=request.force_nodes,
                options=request.options,
                cancel_event=request.cancel_event,
                emit=_emit_wrapper,
            )
            request.result = result
            request.status = (
                RunStatus.COMPLETED
                if result.get("status") == "completed"
                else RunStatus.FAILED
                if result.get("status") == "failed"
                else RunStatus.CANCELLED
            )
        except Exception as exc:
            request.result = {"status": "failed", "error": str(exc)}
            request.status = RunStatus.FAILED
            self.emit("queue_error", {"run_id": request.run_id, "error": str(exc)})

        request.finished_at = time.time()

        async with self._lock:
            active = self._running.pop(request.run_id, request)
            self._history.append(active)

        self.emit(
            "queue_finish",
            {
                "run_id": request.run_id,
                "status": request.status.value,
            },
        )
        await self._emit_queue()

    async def _emit_queue(self) -> None:
        """Broadcast current queue state."""
        self.emit("queue_state", self.queue_state())

    async def _ensure_worker(self) -> None:
        """Start the scheduler exactly once, even under concurrent submits."""
        async with self._worker_start_lock:
            if self._worker_task is None or self._worker_task.done():
                self._worker_task = asyncio.create_task(self._worker())

    def _queue_items(self) -> list[RunRequest]:
        """Return a snapshot of items currently in the pending queue."""
        return list(self._pending_items)

    def _find_request_locked(self, run_id: str) -> RunRequest | None:
        """Find a run while ``self._lock`` is held."""
        for req in self._pending_items:
            if req.run_id == run_id:
                return req
        if run_id in self._running:
            return self._running[run_id]
        for req in self._history:
            if req.run_id == run_id:
                return req
        return None

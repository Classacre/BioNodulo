from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from bionodulo.core.config import Settings
from bionodulo.core.events import event_hub
from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.execution.run_metadata import RunRecord
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.schema import Workflow


@dataclass
class RunRequest:
    run_id: str
    workflow: Workflow
    mock_tools: bool
    force: bool = False
    force_nodes: list[str] = field(default_factory=list)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)


class RunQueue:
    def __init__(self, *, settings: Settings, registry: NodeRegistry) -> None:
        self.settings = settings
        self.registry = registry
        self.queue: asyncio.Queue[RunRequest] = asyncio.Queue()
        self.records: dict[str, RunRecord] = {}
        self.history: list[str] = []
        self.pending: list[str] = []
        self.current: str | None = None
        self._current_request: RunRequest | None = None
        self._counter = count(1)
        self._worker_task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self.executor = WorkflowExecutor(
            registry=registry,
            runs_dir=settings.runs_dir,
            cache_dir=settings.cache_dir,
            emit=event_hub.emit,
        )

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        self._stopping.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def submit(self, workflow: Workflow, *, mock_tools: bool | None = None, force: bool = False, force_nodes: list[str] | None = None) -> RunRecord:
        run_id = self._new_run_id()
        use_mock = self.settings.mock_tools_default if mock_tools is None else mock_tools
        record = RunRecord(run_id=run_id, status="queued", workflow_name=workflow.name, mock_tools=use_mock)
        self.records[run_id] = record
        self.pending.append(run_id)
        await self.queue.put(RunRequest(run_id=run_id, workflow=workflow, mock_tools=use_mock, force=force, force_nodes=force_nodes or []))
        await self._emit_queue()
        return record

    async def interrupt(self, run_id: str) -> bool:
        if self.current == run_id:
            if self._current_request:
                self._current_request.cancel_event.set()
            record = self.records.get(run_id)
            if record:
                record.status = "interrupting"
            return True
        for item in list(self.queue._queue):  # noqa: SLF001 - asyncio.Queue lacks safe pending removal APIs
            if item.run_id == run_id:
                item.cancel_event.set()
                if run_id in self.pending:
                    self.pending.remove(run_id)
                self.records[run_id].status = "interrupted"
                await self._emit_queue()
                return True
        return False

    async def clear_pending(self) -> None:
        while not self.queue.empty():
            try:
                item = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            item.cancel_event.set()
            if item.run_id in self.pending:
                self.pending.remove(item.run_id)
            if item.run_id in self.records:
                self.records[item.run_id].status = "interrupted"
        await self._emit_queue()

    def queue_state(self) -> dict[str, Any]:
        return {"current": self.current, "pending": list(self.pending), "queue_remaining": len(self.pending)}

    def list_runs(self) -> list[dict[str, Any]]:
        return [record.as_dict() for record in sorted(self.records.values(), key=lambda item: item.created_at, reverse=True)]

    def get_run(self, run_id: str) -> RunRecord | None:
        return self.records.get(run_id)

    def list_history(self) -> list[dict[str, Any]]:
        return [self.records[run_id].as_dict() for run_id in self.history if run_id in self.records]

    async def _worker(self) -> None:
        while not self._stopping.is_set():
            item = await self.queue.get()
            if item.run_id in self.pending:
                self.pending.remove(item.run_id)
            self.current = item.run_id
            self._current_request = item
            await self._emit_queue()
            record = self.records[item.run_id]
            try:
                await self.executor.execute(
                    run_id=item.run_id,
                    workflow=item.workflow,
                    record=record,
                    mock_tools=item.mock_tools,
                    force=item.force,
                    force_nodes=item.force_nodes,
                    cancel_event=item.cancel_event,
                )
            finally:
                self.current = None
                self._current_request = None
                self.history.insert(0, item.run_id)
                self.queue.task_done()
                await self._emit_queue()

    async def _emit_queue(self) -> None:
        await event_hub.emit("queue_updated", self.queue_state())
        await event_hub.emit("status", {"exec_info": {"queue_remaining": len(self.pending), "current": self.current}})

    def _new_run_id(self) -> str:
        return f"run-{self._date_prefix()}-{next(self._counter):03d}"

    def _date_prefix(self) -> str:
        from datetime import datetime

        return datetime.now().strftime("%Y%m%d-%H%M%S")

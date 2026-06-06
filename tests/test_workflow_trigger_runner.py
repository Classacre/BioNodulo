from __future__ import annotations

import asyncio
import json

import pytest

from bionodulo.workflow.trigger_runner import WorkflowTriggerRunner


@pytest.mark.asyncio
async def test_workflow_trigger_runner_submits_due_schedule_once(tmp_path) -> None:
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    trigger_file = trigger_dir / "schedule_weekly.json"
    trigger_file.write_text(
        json.dumps(
            {
                "trigger_type": "schedule",
                "status": "registered",
                "target_workflow": "weekly-qc",
                "next_run_at_utc": "2026-06-07T18:30:00+00:00",
                "payload": {"sample": "S1"},
                "workflow": {"name": "Weekly QC", "nodes": [], "edges": []},
            }
        ),
        encoding="utf-8",
    )

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs["run_id"])

    queue = Queue()
    runner = WorkflowTriggerRunner(trigger_dir=trigger_dir, queue=queue)

    first = await runner.evaluate(now="2026-06-07T18:30:00+00:00", submit_runs=True)
    second = await runner.evaluate(now="2026-06-07T18:30:00+00:00", submit_runs=True)

    assert first["due_schedule_count"] == 1
    assert first["submitted_run_count"] == 1
    assert first["submitted_runs"][0]["status"] == "submitted"
    assert queue.submit_calls[0]["workflow"] == {"name": "Weekly QC", "nodes": [], "edges": []}
    assert queue.submit_calls[0]["options"] == {"parameters": {"sample": "S1"}}

    assert second["submitted_run_count"] == 0
    assert second["submitted_runs"][0]["status"] == "skipped"
    assert second["submitted_runs"][0]["reason"] == "already_submitted"
    assert len(queue.submit_calls) == 1

    saved = json.loads(trigger_file.read_text(encoding="utf-8"))
    assert saved["last_submitted_due_at"] == "2026-06-07T18:30:00+00:00"
    assert saved["submitted_run_ids"] == [queue.submit_calls[0]["run_id"]]


@pytest.mark.asyncio
async def test_workflow_trigger_runner_polling_loop_submits_file_watch_events_once(tmp_path) -> None:
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    trigger_file = trigger_dir / "file_watch_inbox.json"
    trigger_file.write_text(
        json.dumps(
            {
                "trigger_type": "file_watch",
                "status": "registered",
                "target_workflow": "auto-import",
                "watch_path": str(watch_dir),
                "watch_event": "create",
                "baseline_snapshot": {},
                "payload": {"project": "P1"},
                "workflow": {"name": "Auto Import", "nodes": [], "edges": []},
            }
        ),
        encoding="utf-8",
    )
    (watch_dir / "new.fastq").write_text("@new\nTGCA\n+\n!!!!\n", encoding="utf-8")

    class Queue:
        def __init__(self) -> None:
            self.submit_calls: list[dict[str, object]] = []

        async def submit(self, **kwargs: object) -> str:
            self.submit_calls.append(kwargs)
            return str(kwargs["run_id"])

    queue = Queue()
    stop_event = asyncio.Event()
    runner = WorkflowTriggerRunner(trigger_dir=trigger_dir, queue=queue)

    result = await runner.run_polling(
        interval_seconds=0.01,
        submit_runs=True,
        stop_event=stop_event,
        max_iterations=2,
    )

    assert result["iterations"] == 2
    assert result["submitted_run_count"] == 1
    assert queue.submit_calls[0]["workflow"] == {"name": "Auto Import", "nodes": [], "edges": []}
    assert queue.submit_calls[0]["options"] == {"parameters": {"project": "P1"}}
    assert queue.submit_calls[0]["metadata"]["trigger_type"] == "file_watch"
    assert queue.submit_calls[0]["metadata"]["target_workflow"] == "auto-import"

    saved = json.loads(trigger_file.read_text(encoding="utf-8"))
    assert saved["submitted_run_ids"] == [queue.submit_calls[0]["run_id"]]
    assert saved["last_submitted_due_at"]
    assert "new.fastq" in saved["baseline_snapshot"]


@pytest.mark.asyncio
async def test_workflow_trigger_runner_does_not_advance_file_watch_baseline_when_submission_fails(tmp_path) -> None:
    trigger_dir = tmp_path / "workflow_triggers"
    trigger_dir.mkdir()
    watch_dir = tmp_path / "inbox"
    watch_dir.mkdir()
    trigger_file = trigger_dir / "file_watch_inbox.json"
    trigger_file.write_text(
        json.dumps(
            {
                "trigger_type": "file_watch",
                "status": "registered",
                "target_workflow": "auto-import",
                "watch_path": str(watch_dir),
                "watch_event": "create",
                "baseline_snapshot": {},
                "payload": {"project": "P1"},
                "workflow": {"name": "Auto Import", "nodes": [], "edges": []},
            }
        ),
        encoding="utf-8",
    )
    new_file = watch_dir / "new.fastq"
    new_file.write_text("@new\nTGCA\n+\n!!!!\n", encoding="utf-8")

    class FailingQueue:
        async def submit(self, **kwargs: object) -> str:
            raise RuntimeError("queue unavailable")

    runner = WorkflowTriggerRunner(trigger_dir=trigger_dir, queue=FailingQueue())

    result = await runner.evaluate(submit_runs=True)

    assert result["submitted_run_count"] == 0
    assert result["errors"] == [
        {
            "kind": "submission",
            "trigger_file": str(trigger_file),
            "error": "queue unavailable",
        }
    ]
    saved = json.loads(trigger_file.read_text(encoding="utf-8"))
    assert "new.fastq" not in saved["baseline_snapshot"]

    retry = await runner.evaluate(submit_runs=False)
    assert retry["due_file_watch_count"] == 1
    assert retry["due_file_watch_triggers"][0]["events"] == [
        {
            "event": "create",
            "path": str(new_file),
            "relative_path": "new.fastq",
        }
    ]

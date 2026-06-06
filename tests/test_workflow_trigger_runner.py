from __future__ import annotations

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

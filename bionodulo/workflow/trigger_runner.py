"""Reusable workflow trigger evaluation and submission helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from bionodulo.core.credentials import redact_tree
from bionodulo.nodes.builtin.workflow_enhancement import WorkflowTriggerNode


RunIdFactory = Callable[[dict[str, Any], dict[str, Any]], str]


class WorkflowTriggerRunner:
    """Poll workflow trigger records and optionally enqueue due workflows."""

    def __init__(
        self,
        *,
        trigger_dir: str | Path,
        queue: Any,
        run_id_factory: RunIdFactory | None = None,
    ) -> None:
        self.trigger_dir = Path(trigger_dir)
        self.queue = queue
        self.run_id_factory = run_id_factory or self._default_run_id

    async def evaluate(self, *, now: str | datetime | None = None, submit_runs: bool = False) -> dict[str, Any]:
        """Return due trigger state and optionally submit embedded workflows."""
        due_schedule_triggers = WorkflowTriggerNode.due_schedule_triggers(self.trigger_dir, now=now)
        due_file_watch_triggers = WorkflowTriggerNode.due_file_watch_triggers(self.trigger_dir)
        submitted_runs: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for trigger in due_file_watch_triggers:
            try:
                self._advance_file_watch_baseline(trigger)
            except Exception as exc:  # noqa: BLE001 - one bad trigger must not abort evaluation
                errors.append({
                    "kind": "file_watch_baseline",
                    "trigger_file": str(trigger.get("trigger_file", "")),
                    "error": str(exc),
                })
        if submit_runs:
            for trigger in [*due_schedule_triggers, *due_file_watch_triggers]:
                try:
                    submitted_runs.append(await self.submit_due_trigger(trigger))
                except Exception as exc:  # noqa: BLE001 - one bad trigger must not abort evaluation
                    errors.append({
                        "kind": "submission",
                        "trigger_file": str(trigger.get("trigger_file", "")),
                        "error": str(exc),
                    })

        return {
            "trigger_dir": str(self.trigger_dir),
            "due_schedule_triggers": due_schedule_triggers,
            "due_schedule_count": len(due_schedule_triggers),
            "due_file_watch_triggers": due_file_watch_triggers,
            "due_file_watch_count": len(due_file_watch_triggers),
            "submitted_runs": submitted_runs,
            "submitted_run_count": sum(1 for item in submitted_runs if item.get("status") == "submitted"),
            "errors": errors,
        }

    @staticmethod
    def _advance_file_watch_baseline(trigger: dict[str, Any]) -> None:
        trigger_file = str(trigger.get("trigger_file", ""))
        if not trigger_file:
            return
        path = Path(str(trigger.get("watch_path", "") or ""))
        persisted = _read_workflow_trigger_file(Path(trigger_file))
        persisted["baseline_snapshot"] = WorkflowTriggerNode._file_watch_snapshot(path) if path.exists() else {}
        persisted["baseline_updated_at"] = datetime.now(timezone.utc).isoformat()
        Path(trigger_file).write_text(json.dumps(persisted, indent=2, sort_keys=True, default=str), encoding="utf-8")

    async def submit_due_trigger(self, trigger: dict[str, Any]) -> dict[str, Any]:
        """Submit one due trigger to the queue, idempotent for the same due marker."""
        trigger_file = str(trigger.get("trigger_file", ""))
        due_marker = _trigger_due_marker(trigger)
        if due_marker and trigger.get("last_submitted_due_at") == due_marker:
            return {
                "trigger_file": trigger_file,
                "status": "skipped",
                "reason": "already_submitted",
                "due_at": due_marker,
            }

        workflow = _embedded_trigger_workflow(trigger)
        if workflow is None:
            return {
                "trigger_file": trigger_file,
                "status": "skipped",
                "reason": "missing_embedded_workflow",
                "due_at": due_marker,
            }

        run_id = self.run_id_factory(workflow, trigger)
        payload = trigger.get("payload") if isinstance(trigger.get("payload"), dict) else {}
        parameters = {
            key: value
            for key, value in payload.items()
            if key != "workflow"
        }
        redacted_parameters = redact_tree(parameters)
        metadata = {
            "trigger_type": trigger.get("trigger_type", ""),
            "target_workflow": trigger.get("target_workflow", ""),
            "trigger_file": trigger_file,
            "due_at": due_marker,
            "payload": redacted_parameters,
        }
        await self.queue.submit(
            workflow=workflow,
            run_id=run_id,
            options={"parameters": parameters} if parameters else {},
            metadata=metadata,
        )

        if trigger_file:
            self._persist_submission(Path(trigger_file), due_marker, run_id)

        return {
            "trigger_file": trigger_file,
            "status": "submitted",
            "run_id": run_id,
            "due_at": due_marker,
        }

    @staticmethod
    def _persist_submission(trigger_file: Path, due_marker: str, run_id: str) -> None:
        try:
            persisted = _read_workflow_trigger_file(trigger_file)
        except ValueError:
            return
        submitted_ids = persisted.get("submitted_run_ids", [])
        if not isinstance(submitted_ids, list):
            submitted_ids = []
        persisted["submitted_run_ids"] = [*submitted_ids, run_id]
        persisted["last_submitted_due_at"] = due_marker
        persisted["last_submitted_run_id"] = run_id
        persisted["last_submitted_at"] = datetime.now(timezone.utc).isoformat()
        trigger_file.write_text(json.dumps(persisted, indent=2, sort_keys=True, default=str), encoding="utf-8")

    @staticmethod
    def _default_run_id(workflow: dict[str, Any], trigger: dict[str, Any]) -> str:
        workflow_name = str(workflow.get("name") or trigger.get("target_workflow") or "triggered_workflow")
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in workflow_name)[:30]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:6]
        return f"{safe_name}_{ts}_{short_uuid}"


def _read_workflow_trigger_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"workflow trigger file is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"workflow trigger file must contain a JSON object: {path}")
    data.setdefault("trigger_file", str(path))
    return data


def _trigger_due_marker(trigger: dict[str, Any]) -> str:
    if trigger.get("trigger_type") == "schedule":
        return str(trigger.get("next_run_at_utc", "") or trigger.get("next_run_at", "") or "")
    events = trigger.get("events", [])
    return json.dumps(events, sort_keys=True, default=str) if isinstance(events, list) else str(events)


def _embedded_trigger_workflow(trigger: dict[str, Any]) -> dict[str, Any] | None:
    workflow = trigger.get("workflow")
    if isinstance(workflow, dict):
        return workflow
    payload = trigger.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("workflow"), dict):
        return payload["workflow"]
    return None

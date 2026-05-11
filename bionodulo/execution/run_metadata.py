"""RunRecord dataclass for tracking workflow execution metadata.

Provides structured storage for run state, node statuses, outputs,
and timing information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    """Execution status of a workflow run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(str, Enum):
    """Execution status of an individual node."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class NodeExecutionRecord:
    """Execution record for a single node instance.

    Tracks timing, status, outputs, and any error information.
    """

    node_id: str
    node_type: str = ""
    status: NodeStatus = NodeStatus.PENDING
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    command: str = ""
    cached: bool = False
    cache_hit: bool = False
    started_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        if self.started_at:
            return (utc_now() - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status.value,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "command": self.command,
            "cached": self.cached,
            "cache_hit": self.cache_hit,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class ExecutionPlan:
    """The execution plan for a workflow run.

    Contains the topologically sorted node order and any parallel
    execution groups.
    """

    node_order: list[str] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_order": self.node_order,
            "parallel_groups": self.parallel_groups,
            "dependencies": self.dependencies,
        }


@dataclass
class ArtifactRecord:
    """An artifact produced during workflow execution.

    Artifacts include output files, logs, reports, and previews.
    """

    name: str
    path: str
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    node_id: str = ""
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "node_id": self.node_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class RunRecord:
    """Complete execution record for a workflow run.

    Contains all metadata needed to track, audit, and reproduce a run.
    """

    run_id: str
    status: RunStatus = RunStatus.QUEUED
    workflow_name: str = "Untitled"
    workflow: dict[str, Any] = field(default_factory=dict)
    node_statuses: dict[str, NodeExecutionRecord] = field(default_factory=dict)
    node_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    previews: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[ArtifactRecord] = field(default_factory=list)
    settings_snapshot: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error_message: str = ""

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        if self.started_at:
            return (utc_now() - self.started_at).total_seconds()
        return None

    @property
    def progress(self) -> float:
        if not self.node_statuses:
            return 0.0
        total = len(self.node_statuses)
        done = sum(
            1
            for r in self.node_statuses.values()
            if r.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED, NodeStatus.CACHED)
        )
        return done / total if total > 0 else 0.0

    def start(self) -> None:
        """Mark the run as started."""
        self.status = RunStatus.RUNNING
        self.started_at = utc_now()

    def complete(self) -> None:
        """Mark the run as completed successfully."""
        self.status = RunStatus.COMPLETED
        self.ended_at = utc_now()

    def fail(self, message: str = "") -> None:
        """Mark the run as failed."""
        self.status = RunStatus.FAILED
        self.ended_at = utc_now()
        self.error_message = message

    def cancel(self) -> None:
        """Mark the run as cancelled."""
        self.status = RunStatus.CANCELLED
        self.ended_at = utc_now()

    def update_node(
        self,
        node_id: str,
        status: NodeStatus | None = None,
        outputs: dict[str, Any] | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        """Update the status and outputs of a specific node."""
        if node_id not in self.node_statuses:
            self.node_statuses[node_id] = NodeExecutionRecord(node_id=node_id)

        record = self.node_statuses[node_id]
        if status is not None:
            record.status = status
            if status == NodeStatus.RUNNING and record.started_at is None:
                record.started_at = utc_now()
            if status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED):
                record.ended_at = utc_now()

        if outputs is not None:
            record.outputs.update(outputs)
            self.node_outputs[node_id] = record.outputs

        if stdout is not None:
            record.stdout += stdout

        if stderr is not None:
            record.stderr += stderr

    def add_artifact(self, artifact: ArtifactRecord) -> None:
        """Add an artifact to the run record."""
        if artifact.created_at is None:
            artifact.created_at = utc_now()
        self.artifacts.append(artifact)

    def add_preview(self, preview: dict[str, Any]) -> None:
        """Add a preview item to the run record."""
        self.previews.append(preview)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the run record to a dictionary."""
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "workflow_name": self.workflow_name,
            "node_statuses": {
                nid: rec.to_dict() for nid, rec in self.node_statuses.items()
            },
            "node_outputs": self.node_outputs,
            "execution_plan": self.execution_plan.to_dict(),
            "previews": self.previews,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "progress": self.progress,
            "error_message": self.error_message,
        }

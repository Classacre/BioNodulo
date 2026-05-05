from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunRecord:
    run_id: str
    status: str
    workflow_name: str
    mock_tools: bool
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    ended_at: str | None = None
    run_dir: str | None = None
    node_statuses: dict[str, str] = field(default_factory=dict)
    node_outputs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "workflow_name": self.workflow_name,
            "mock_tools": self.mock_tools,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "run_dir": self.run_dir,
            "node_statuses": self.node_statuses,
            "node_outputs": self.node_outputs,
            "error": self.error,
        }

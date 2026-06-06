"""File-backed pause/resume request state."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class PauseStateStore:
    """Persist and resolve pause/resume review requests as JSON files."""

    def __init__(self, pause_dir: str | Path) -> None:
        self.pause_dir = Path(pause_dir)

    def path_for(self, run_id: str, node_id: str) -> Path:
        run_id = str(run_id or "").strip()
        node_id = str(node_id or "").strip()
        if not node_id:
            raise ValueError("node_id is required")
        filename = f"{run_id}__{node_id}.json" if run_id else f"{node_id}.json"
        return self.pause_dir / filename

    def save(self, pause_info: dict[str, Any]) -> Path:
        self.pause_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(
            str(pause_info.get("run_id", "") or ""),
            str(pause_info.get("node_id", "") or ""),
        )
        payload = dict(pause_info)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path

    def load(self, pause_file: str | Path) -> dict[str, Any]:
        path = Path(pause_file)
        if not path.exists():
            raise FileNotFoundError(f"pause request was not found: {path}")
        try:
            pause_info = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"pause request file is not valid JSON: {path}") from exc
        if not isinstance(pause_info, dict):
            raise ValueError(f"pause request file must contain a JSON object: {path}")
        pause_info.setdefault("pause_file", str(path))
        return pause_info

    def load_by_run_node(self, run_id: str, node_id: str) -> dict[str, Any]:
        return self.load(self.path_for(run_id, node_id))

    def resolve(
        self,
        *,
        action: str,
        reviewer: str = "",
        comment: str = "",
        pause_file: str | Path | None = None,
        run_id: str = "",
        node_id: str = "",
    ) -> dict[str, Any]:
        action = str(action or "").lower().strip()
        if action not in {"approve", "reject"}:
            raise ValueError(f"Unsupported pause resolution action: {action}")
        path = Path(pause_file) if pause_file is not None else self.path_for(run_id, node_id)
        pause_info = self.load(path)
        approved = action == "approve"
        pause_info.update(
            {
                "status": "approved" if approved else "rejected",
                "approved": approved,
                "resolved_at": time.time(),
                "resolved_by": str(reviewer or "").strip(),
                "resolution_comment": str(comment or ""),
                "review_decision_supported": True,
                "engine_pause_supported": True,
                "note": "Review request recorded with persistent approval metadata; executor-level blocking pause/resume is supported.",
            }
        )
        path.write_text(json.dumps(pause_info, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return dict(pause_info)

    def cancel(self, pause_file: str | Path) -> dict[str, Any]:
        path = Path(pause_file)
        pause_info = self.load(path)
        pause_info.update(
            {
                "pause_file": str(path),
                "status": "cancelled",
                "approved": False,
                "resolved_at": time.time(),
                "review_decision_supported": True,
                "engine_pause_supported": True,
                "note": "Review request cancelled while waiting for approval.",
            }
        )
        path.write_text(json.dumps(pause_info, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return dict(pause_info)

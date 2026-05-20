"""Persistence layer for collaborative workflow state.

Provides save / load operations for the JSON-based document state
used by the MVP collaborative sync. Files are stored under
``workspace/collab/{workflow_id}.json``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import aiofiles

logger = logging.getLogger(__name__)

DEFAULT_EMPTY_STATE: dict[str, Any] = {
    "meta": {
        "id": "",
        "version": 1,
        "name": "Untitled",
        "createdAt": "",
        "createdBy": "",
        "lastModified": "",
    },
    "nodes": {},
    "edges": {},
    "groups": {},
    "viewport": {"x": 0, "y": 0, "scale": 1.0},
}


def _collab_dir(root: Path) -> Path:
    directory = root / "collab"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _workflow_path(workflow_id: str, root: Path) -> Path:
    return _collab_dir(root) / f"{workflow_id}.json"


async def save_workflow_state(
    workflow_id: str,
    state: dict[str, Any],
    root: Path | None = None,
) -> None:
    """Persist a workflow's collaborative state to disk.

    Args:
        workflow_id: Unique workflow identifier.
        state: Document state dict (nodes, edges, groups, viewport, meta).
        root: Base directory; defaults to the BIONODULO_ROOT workspace.
    """
    if root is None:
        root = _resolve_workspace_root()

    path = _workflow_path(workflow_id, root)
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
        await f.write(payload)
    logger.debug("Saved workflow state for %s (%d bytes)", workflow_id, len(payload))


async def load_workflow_state(
    workflow_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Load a workflow's collaborative state from disk.

    Returns an empty default state if the file does not exist yet.
    """
    if root is None:
        root = _resolve_workspace_root()

    path = _workflow_path(workflow_id, root)
    if not path.exists():
        state = dict(DEFAULT_EMPTY_STATE)
        state["meta"]["id"] = workflow_id
        state["meta"]["createdAt"] = ""
        return state

    try:
        async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
            content = await f.read()
        data = json.loads(content)
        # Ensure all expected top-level keys exist
        for key in DEFAULT_EMPTY_STATE:
            if key not in data:
                data[key] = dict(DEFAULT_EMPTY_STATE[key])  # type: ignore[arg-type]
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load workflow state for %s: %s", workflow_id, exc)
        state = dict(DEFAULT_EMPTY_STATE)
        state["meta"]["id"] = workflow_id
        return state


async def save_workflow_json(
    workflow_id: str,
    json_data: dict[str, Any],
    root: Path | None = None,
) -> Path:
    """Export a workflow to standard JSON format (non-collab).

    Useful for creating snapshots or downloadable exports.
    """
    if root is None:
        root = _resolve_workspace_root()

    export_dir = root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"{workflow_id}.json"
    async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
        await f.write(json.dumps(json_data, ensure_ascii=False, indent=2))
    return path


def _resolve_workspace_root() -> Path:
    """Resolve the BioNodulo workspace root from environment."""
    import os

    root = os.environ.get("BIONODULO_ROOT", "")
    if root:
        return Path(root)
    # Fallback: project_dir/workspace
    project_dir = Path(__file__).resolve().parent.parent.parent
    return (project_dir / "workspace").resolve()

"""Preview image serving endpoints for BioNodulo.

Allows the frontend to retrieve preview images generated during workflow
execution (e.g., R plots, QC images).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter()


def _preview_root(request: Request) -> Path | None:
    """The directory a preview file MUST live under (audit M3).

    Previews are produced by workflow runs and live beneath the project root
    (runs/outputs/workspace). Containing served files to this root prevents the
    unbounded arbitrary-file-read that existed when `path` flowed straight into
    FileResponse (e.g. ``?path=/proc/self/environ`` leaked the process env).
    """
    settings = getattr(request.app.state, "settings", None)
    root = getattr(settings, "project_root", None)
    return Path(root).resolve() if root else None


def _contain(path: str, root: Path) -> Path | None:
    """Resolve `path` and return it only if it lands within `root`.

    Preview paths are stored ABSOLUTE (register_preview stashes the run's output
    path), so — unlike ensure_within — an absolute path already under the root is
    valid; anything that resolves outside the root (traversal, or an unrelated
    absolute path like /etc/passwd) returns None. Symlinks are resolved first so
    a symlink inside the root can't point out of it.
    """
    try:
        candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    except (OSError, ValueError):
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


@router.get("/previews/{run_id}/{node_id}")
async def get_preview(request: Request, run_id: str, node_id: str, path: str = "") -> Any:
    """Serve a preview image/file for a specific run and node.

    Query param `path` is a path to the preview file. It is CONTAINED to the
    project root (audit M3): a path that resolves outside the root — whether
    supplied by the caller or read back from the run record — is rejected.
    """
    if not path:
        # Try to look up from run record
        queue = getattr(request.app.state, "run_queue", None)
        run = None
        if queue and hasattr(queue, "get_run"):
            run = queue.get_run(run_id)
        if run and run.get("result"):
            result = run["result"]
            previews = result.get("previews", []) if isinstance(result.get("previews"), list) else []
            for p in previews:
                if p.get("node_id") == node_id:
                    path = p.get("path", "")
                    break
        if not path:
            raise HTTPException(status_code=404, detail="Preview path not found")

    # Containment: resolve `path` under the project root and reject any escape.
    root = _preview_root(request)
    if root is None:
        raise HTTPException(status_code=404, detail="Preview root unavailable")
    file_path = _contain(path, root)
    if file_path is None:
        # Traversal / absolute path outside the root → 403, no filesystem probe.
        raise HTTPException(status_code=403, detail="Preview path not permitted")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Preview file not found")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=media_type or "application/octet-stream")

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


@router.get("/previews/{run_id}/{node_id}")
async def get_preview(request: Request, run_id: str, node_id: str, path: str = "") -> Any:
    """Serve a preview image/file for a specific run and node.

    Query param `path` is the absolute or relative path to the preview file.
    """
    if not path:
        # Try to look up from run record
        queue = getattr(request.app.state, "run_queue", None)
        run = None
        if queue and hasattr(queue, "get_run"):
            run = await queue.get_run(run_id)
        if run and "previews" in run and node_id in run["previews"]:
            path = run["previews"][node_id]
        else:
            raise HTTPException(status_code=404, detail="Preview path not found")

    file_path = Path(path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview file not found")

    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(str(file_path), media_type=media_type or "application/octet-stream")

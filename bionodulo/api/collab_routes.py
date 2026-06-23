"""Phase 3 REST API endpoints for BioNodulo collaboration features.

Provides routes for:
- Comments (CRUD + resolve)
- Workflow versions (save, list, restore, diff, delete)
- Audit logging (query, export CSV, summary)
- Template gallery (list, create, fork, delete)

All endpoints (except public template listing) require JWT authentication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from bionodulo.api.app_state import app_state
from bionodulo.api.collab_dependencies import require_workflow_role
from bionodulo.api.schemas import (
    CreateTemplateRequest,
    CreateVersionRequest,
)
from bionodulo.collab.audit import AuditLogger
from bionodulo.collab.auth import validate_token
from bionodulo.collab.doc_store import extract_flat_snapshot, get_or_create_doc_async, load_doc_from_db_async

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

security_scheme = HTTPBearer(auto_error=False)


async def get_token_from_header_or_query(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict[str, Any]:
    """Extract and validate a JWT from the Authorization header or ?token= query param.

    Returns the decoded payload dict, or raises HTTPException(401).
    """
    token: str | None = None

    # Try Authorization header first
    if credentials is not None:
        token = credentials.credentials
    else:
        # Fall back to query parameter
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    payload = validate_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")

    return payload


# ---------------------------------------------------------------------------
# Dependency helpers — resolved per-request via Request.app.state
# ---------------------------------------------------------------------------


def _get_collab_store(request: Request) -> Any:
    """Get or create the shared CollabStore instance."""
    return app_state(request).collab_store


def _get_audit_logger(request: Request) -> AuditLogger:
    """Get or create the AuditLogger instance."""
    return app_state(request).audit_logger


def _get_template_manager(request: Request) -> Any:
    """Get or create the TemplateManager instance."""
    return app_state(request).template_manager


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

collab_api_router = APIRouter(prefix="/collab", tags=["collaboration"])


# ============================================================================
# Versions
# ============================================================================


@collab_api_router.post("/workflows/{workflow_id}/versions", status_code=201)
async def create_version(
    workflow_id: str,
    body: CreateVersionRequest,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Save a manual version snapshot."""
    store = _get_collab_store(request)
    user_id = token_payload.get("sub", "")
    require_workflow_role(request, workflow_id, user_id, "write")

    doc = await load_doc_from_db_async(workflow_id)
    if doc is None:
        doc = await get_or_create_doc_async(workflow_id)

    snapshot = extract_flat_snapshot(doc)

    version_name = body.name or f"Version {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    from bionodulo.collab.models import WorkflowVersion
    version = WorkflowVersion(
        workflow_id=workflow_id,
        name=version_name,
        snapshot=snapshot,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        auto_save=False,
    )
    store.add_version(version)

    await _get_audit_logger(request).log(
        workflow_id=workflow_id,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="version_save",
        target_type="workflow",
        target_id=workflow_id,
        payload={"version_id": version.id, "version_name": version_name},
    )

    return version.to_dict()


@collab_api_router.get("/workflows/{workflow_id}/versions")
async def list_versions(
    workflow_id: str,
    request: Request,
    limit: int = 50,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """List version history."""
    store = _get_collab_store(request)
    user_id = token_payload.get("sub", "")
    require_workflow_role(request, workflow_id, user_id, "read")

    versions = store.list_versions(workflow_id, limit=limit)
    return {"versions": [v.to_dict() for v in versions], "count": len(versions)}


@collab_api_router.post("/versions/{version_id}/restore")
async def restore_version(
    version_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Restore a version — returns snapshot JSON for the client to load."""
    store = _get_collab_store(request)

    version = store.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    user_id = token_payload.get("sub", "")
    require_workflow_role(request, version.workflow_id, user_id, "write")

    await _get_audit_logger(request).log(
        workflow_id=version.workflow_id,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="version_restore",
        target_type="workflow",
        target_id=version.workflow_id,
        payload={"version_id": version_id, "version_name": version.name},
    )

    return {
        "version_id": version.id,
        "name": version.name,
        "snapshot": version.snapshot,
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


@collab_api_router.get("/versions/{version_id_a}/diff/{version_id_b}")
async def diff_versions(
    version_id_a: str,
    version_id_b: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Compare two version snapshots."""
    store = _get_collab_store(request)

    v_a = store.get_version(version_id_a)
    v_b = store.get_version(version_id_b)
    if v_a is None:
        raise HTTPException(status_code=404, detail=f"Version {version_id_a} not found")
    if v_b is None:
        raise HTTPException(status_code=404, detail=f"Version {version_id_b} not found")
    if v_a.workflow_id != v_b.workflow_id:
        raise HTTPException(status_code=400, detail="Versions belong to different workflows")

    user_id = token_payload.get("sub", "")
    require_workflow_role(request, v_a.workflow_id, user_id, "read")

    snap_a = v_a.snapshot if isinstance(v_a.snapshot, dict) else {}
    snap_b = v_b.snapshot if isinstance(v_b.snapshot, dict) else {}
    return _diff_snapshots(snap_a, snap_b)


def _diff_map_ids(snap_a: dict[str, Any], snap_b: dict[str, Any], key: str) -> dict[str, list[str]]:
    before = snap_a.get(key, {})
    after = snap_b.get(key, {})
    if not isinstance(before, dict):
        before = {}
    if not isinstance(after, dict):
        after = {}

    before_ids = set(before.keys())
    after_ids = set(after.keys())
    common_ids = before_ids & after_ids
    return {
        "added": sorted(after_ids - before_ids),
        "removed": sorted(before_ids - after_ids),
        "modified": sorted(item_id for item_id in common_ids if before[item_id] != after[item_id]),
        "common": sorted(item_id for item_id in common_ids if before[item_id] == after[item_id]),
    }


def _diff_snapshots(snap_a: dict[str, Any], snap_b: dict[str, Any]) -> dict[str, Any]:
    """Return the frontend VersionDiffResult shape."""
    result: dict[str, Any] = {
        "nodes": _diff_map_ids(snap_a, snap_b, "nodes"),
        "edges": _diff_map_ids(snap_a, snap_b, "edges"),
        "groups": _diff_map_ids(snap_a, snap_b, "groups"),
        "meta_changes": {},
    }

    for key in ("meta", "viewport"):
        before = snap_a.get(key, {})
        after = snap_b.get(key, {})
        if before != after:
            result["meta_changes"][key] = {"before": before, "after": after}
    return result


@collab_api_router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_version(
    version_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> None:
    """Delete a version."""
    store = _get_collab_store(request)

    version = store.get_version(version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Version not found")

    user_id = token_payload.get("sub", "")
    require_workflow_role(request, version.workflow_id, user_id, "write")

    store.delete_version(version_id)

    await _get_audit_logger(request).log(
        workflow_id=version.workflow_id,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="version_delete",
        target_type="workflow",
        target_id=version.workflow_id,
        payload={"version_id": version_id},
    )


# ============================================================================
# Audit
# ============================================================================


@collab_api_router.get("/workflows/{workflow_id}/audit")
async def query_audit(
    workflow_id: str,
    request: Request,
    user_id: str | None = None,
    action: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Query audit log with filters."""
    caller_id = token_payload.get("sub", "")
    require_workflow_role(request, workflow_id, caller_id, "read")

    audit_logger = _get_audit_logger(request)
    entries = await audit_logger.query(
        workflow_id=workflow_id,
        user_id=user_id,
        action=action,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return {"entries": [e.to_dict() for e in entries], "count": len(entries)}


@collab_api_router.get("/workflows/{workflow_id}/audit/export")
async def export_audit_csv(
    workflow_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> PlainTextResponse:
    """Export audit log as CSV."""
    caller_id = token_payload.get("sub", "")
    require_workflow_role(request, workflow_id, caller_id, "read")

    audit_logger = _get_audit_logger(request)
    csv_data = await audit_logger.export_csv(workflow_id=workflow_id)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit_{workflow_id}.csv"'},
    )


@collab_api_router.get("/workflows/{workflow_id}/audit/summary")
async def audit_summary(
    workflow_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Get audit summary statistics."""
    caller_id = token_payload.get("sub", "")
    require_workflow_role(request, workflow_id, caller_id, "read")

    audit_logger = _get_audit_logger(request)
    return await audit_logger.get_summary(workflow_id)


# ============================================================================
# Templates
# ============================================================================


@collab_api_router.get("/templates")
async def list_templates(
    request: Request,
    search: str | None = None,
    tags: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List public templates. No auth required."""
    manager = _get_template_manager(request)
    templates = await manager.list_public(search=search, tags=tags, limit=limit)
    return {"templates": [t.to_dict() for t in templates], "count": len(templates)}


@collab_api_router.post("/templates", status_code=201)
async def create_template(
    body: CreateTemplateRequest,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Save a workflow as a template."""
    user_id = token_payload.get("sub", "")
    require_workflow_role(request, body.workflow_id, user_id, "write")

    manager = _get_template_manager(request)
    template_id = await manager.create(
        workflow_id=body.workflow_id,
        user_id=user_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        doc=None,
        is_public=body.is_public,
    )

    await _get_audit_logger(request).log(
        workflow_id=body.workflow_id,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="template_create",
        target_type="workflow",
        target_id=body.workflow_id,
        payload={"template_id": template_id, "title": body.title, "is_public": body.is_public},
    )

    return {"template_id": template_id, "status": "created"}


@collab_api_router.post("/templates/{template_id}/fork", status_code=201)
async def fork_template(
    template_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> dict[str, Any]:
    """Fork a template into a new workflow."""
    manager = _get_template_manager(request)

    user_id = token_payload.get("sub", "")
    new_workflow_id = await manager.fork(template_id, user_id)
    if new_workflow_id is None:
        raise HTTPException(status_code=404, detail="Template not found")

    await _get_audit_logger(request).log(
        workflow_id=new_workflow_id,
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="template_fork",
        target_type="workflow",
        target_id=new_workflow_id,
        payload={"template_id": template_id},
    )

    return {
        "workflow_id": new_workflow_id,
        "template_id": template_id,
        "status": "forked",
    }


@collab_api_router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_template(
    template_id: str,
    request: Request,
    token_payload: dict[str, Any] = Depends(get_token_from_header_or_query),
) -> None:
    """Delete a template (only by creator)."""
    manager = _get_template_manager(request)

    user_id = token_payload.get("sub", "")
    template = await manager.get(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if template.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this template")

    success = await manager.delete(template_id, user_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete template")

    await _get_audit_logger(request).log(
        workflow_id="",
        user_id=user_id,
        user_name=token_payload.get("name", ""),
        action="template_delete",
        target_type="workflow",
        target_id=template_id,
    )

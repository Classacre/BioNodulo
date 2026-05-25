"""Template gallery management for BioNodulo workflows.

Provides CRUD operations and forking for workflow templates stored in
SQLite. Templates capture a point-in-time snapshot of a workflow that can
be shared publicly and forked by other users.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import pycrdt

from bionodulo.collab.models import CollabStore, WorkflowTemplate
from bionodulo.collab.doc_store import (
    apply_flat_snapshot,
    extract_flat_snapshot,
    get_or_create_doc_async,
    load_doc_from_db_async,
    persist_doc_update_async,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TemplateManager
# ---------------------------------------------------------------------------


class TemplateManager:
    """Manage workflow templates: create, list, fork, delete.

    Uses :class:`bionodulo.collab.models.CollabStore` for template metadata
    and :mod:`bionodulo.collab.doc_store` for CRDT snapshot storage.
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._store = CollabStore(db_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _doc_snapshot(self, workflow_id: str) -> dict[str, Any]:
        """Extract a JSON-serialisable snapshot from a CRDT document."""
        doc = await load_doc_from_db_async(workflow_id)
        if doc is None:
            doc = await get_or_create_doc_async(workflow_id)
        return extract_flat_snapshot(doc)

    def _workflow_id_from_doc(self, snapshot: dict[str, Any]) -> str:
        """Generate a new workflow ID for a forked template."""
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(
        self,
        workflow_id: str,
        user_id: str,
        title: str,
        description: str,
        tags: str,
        doc: pycrdt.Doc | None = None,
        is_public: bool = False,
    ) -> str:
        """Save a workflow as a template.

        Args:
            workflow_id: Source workflow identifier.
            user_id: Creator user identifier.
            title: Human-readable template title.
            description: Template description.
            tags: Comma-separated tag string.
            doc: Optional CRDT document to snapshot.
            is_public: Whether the template is publicly visible.

        Returns:
            The new template ID.
        """
        template_id = str(uuid.uuid4())

        # Build snapshot from doc or load from DB
        if doc is not None:
            snapshot = extract_flat_snapshot(doc)
        else:
            snapshot = await self._doc_snapshot(workflow_id)

        # Enrich snapshot meta with template provenance
        snapshot.setdefault("meta", {})
        snapshot["meta"]["template_id"] = template_id
        snapshot["meta"]["templated_at"] = datetime.now(timezone.utc).isoformat()
        snapshot["meta"]["templated_by"] = user_id

        template = WorkflowTemplate(
            id=template_id,
            workflow_id=workflow_id,
            title=title,
            description=description,
            tags=tags,
            is_public=is_public,
            user_id=user_id,
            fork_count=0,
            created_at=datetime.now(timezone.utc).isoformat(),
            snapshot=snapshot,
        )
        self._store.add_template(template)
        logger.info("Created template %s from workflow %s by %s", template_id, workflow_id, user_id)
        return template_id

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_public(
        self,
        search: str | None = None,
        tags: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WorkflowTemplate]:
        """List public templates with optional search and tag filter."""
        return self._store.list_public_templates(search=search, tags=tags, limit=limit, offset=offset)

    async def list_user(self, user_id: str, limit: int = 50) -> list[WorkflowTemplate]:
        """List templates created by a user."""
        return self._store.list_user_templates(user_id=user_id, limit=limit)

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    async def get(self, template_id: str) -> WorkflowTemplate | None:
        """Get a single template by ID."""
        return self._store.get_template(template_id)

    # ------------------------------------------------------------------
    # Fork
    # ------------------------------------------------------------------

    async def fork(self, template_id: str, user_id: str) -> str | None:
        """Fork a template into a new workflow.

        Copies the template snapshot into a new CRDT document and returns
        the new workflow ID.

        Args:
            template_id: The template to fork.
            user_id: The user performing the fork.

        Returns:
            The new workflow ID, or None if the template was not found.
        """
        template = self._store.get_template(template_id)
        if template is None:
            logger.warning("Fork failed: template %s not found", template_id)
            return None

        new_workflow_id = str(uuid.uuid4())
        snapshot = template.snapshot if isinstance(template.snapshot, dict) else {}

        # Create a new CRDT document from the snapshot
        doc = pycrdt.Doc()
        fork_snapshot = {
            **snapshot,
            "meta": {
                **snapshot.get("meta", {}),
                "id": new_workflow_id,
                "forked_from": template_id,
                "forked_by": user_id,
                "forked_at": datetime.now(timezone.utc).isoformat(),
                "name": f"Fork of {template.title}",
                "version": 1,
            },
            "nodes": snapshot.get("nodes", {}),
            "edges": snapshot.get("edges", {}),
            "groups": snapshot.get("groups", {}),
            "viewport": snapshot.get("viewport", {"x": 0, "y": 0, "scale": 1.0}),
        }
        apply_flat_snapshot(doc, fork_snapshot)

        # Persist the initial state as a full update
        full_update = doc.get_update(b"\x00")
        await persist_doc_update_async(new_workflow_id, full_update)

        # Increment fork counter
        self._store.increment_template_forks(template_id)

        logger.info(
            "Forked template %s into new workflow %s by %s",
            template_id,
            new_workflow_id,
            user_id,
        )
        return new_workflow_id

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, template_id: str, user_id: str) -> bool:
        """Delete a template (only allowed by the creator).

        Args:
            template_id: The template to delete.
            user_id: The requesting user.

        Returns:
            True if deleted, False if not found or not authorized.
        """
        template = self._store.get_template(template_id)
        if template is None:
            return False
        if template.user_id != user_id:
            logger.warning(
                "User %s attempted to delete template %s owned by %s",
                user_id,
                template_id,
                template.user_id,
            )
            return False
        return self._store.delete_template(template_id, user_id)

    # ------------------------------------------------------------------
    # Increment fork count
    # ------------------------------------------------------------------

    async def increment_fork_count(self, template_id: str) -> None:
        """Increment the fork counter for a template."""
        self._store.increment_template_forks(template_id)

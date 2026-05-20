"""Permission checker for collaborative editing rooms.

Implements a simple in-memory + JSON-file persistence model for MVP.
All operations are async-safe because the data is protected by the
event-loop's single-thread semantics.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from bionodulo.collab.models import CollabStore, WorkflowShare

logger = logging.getLogger(__name__)

# Role precedence (higher index = more privileges)
_ROLE_RANK = {"viewer": 0, "commenter": 1, "editor": 2, "owner": 3}


class PermissionChecker:
    """Check and manage collaboration permissions for workflows.

    For MVP permissions are stored in-memory with periodic JSON backup.
    The ``CollabStore`` SQLite backend is used for durable shares.
    """

    def __init__(
        self,
        store: CollabStore | None = None,
        fallback_file: Path | None = None,
    ) -> None:
        self._store = store or CollabStore(":memory:")
        self._fallback_file = fallback_file
        self._cache: dict[str, dict[str, str]] = {}  # workflow_id -> {user_id: role}
        if fallback_file and fallback_file.exists():
            try:
                raw = json.loads(fallback_file.read_text(encoding="utf-8"))
                self._cache = raw.get("permissions", {})
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Could not load permission cache: %s", exc)

    # ------------------------------------------------------------------
    # Core checks
    # ------------------------------------------------------------------

    def can_read(self, workflow_id: str, user_id: str) -> bool:
        """Return True if the user has any role on the workflow."""
        role = self.get_role(workflow_id, user_id)
        return role is not None

    def can_write(self, workflow_id: str, user_id: str) -> bool:
        """Return True if user is editor or owner."""
        role = self.get_role(workflow_id, user_id)
        return role in ("editor", "owner")

    def can_comment(self, workflow_id: str, user_id: str) -> bool:
        """Return True if user can add comments without editing the graph."""
        role = self.get_role(workflow_id, user_id)
        return role in ("commenter", "editor", "owner")

    def can_execute(self, workflow_id: str, user_id: str) -> bool:
        """Return True if user is editor or owner."""
        return self.can_write(workflow_id, user_id)

    def can_share(self, workflow_id: str, user_id: str) -> bool:
        """Return True if user is owner."""
        role = self.get_role(workflow_id, user_id)
        return role == "owner"

    def get_role(self, workflow_id: str, user_id: str) -> str | None:
        """Resolve the user's role, falling back to cached / in-memory data."""
        # 1. In-memory cache
        cached = self._cache.get(workflow_id, {}).get(user_id)
        if cached:
            return cached

        # 2. SQLite store
        db_role = self._store.get_user_role(workflow_id, user_id)
        if db_role:
            # Warm cache
            self._cache.setdefault(workflow_id, {})[user_id] = db_role
            return db_role

        # 3. Default: first user to touch a workflow becomes owner
        #    (MVP heuristic — no real auth system yet)
        return None

    def ensure_owner(self, workflow_id: str, user_id: str) -> None:
        """Ensure the user is registered as owner if no owner exists yet."""
        existing = self._store.list_shares(workflow_id)
        has_owner = any(s.role == "owner" for s in existing)
        if not has_owner:
            share = WorkflowShare(
                workflow_id=workflow_id,
                user_id=user_id,
                role="owner",
                invited_by=user_id,
            )
            self._store.add_share(share)
            self._cache.setdefault(workflow_id, {})[user_id] = "owner"
            logger.info("Auto-assigned owner for workflow %s to user %s", workflow_id, user_id)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def grant(
        self,
        workflow_id: str,
        user_id: str,
        role: str,
        invited_by: str = "",
    ) -> WorkflowShare:
        """Grant a role to a user on a workflow."""
        if role not in _ROLE_RANK:
            raise ValueError(f"Invalid role: {role}")
        share = WorkflowShare(
            workflow_id=workflow_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
        )
        self._store.add_share(share)
        self._cache.setdefault(workflow_id, {})[user_id] = role
        self._persist_cache()
        return share

    def revoke(self, workflow_id: str, user_id: str) -> bool:
        """Revoke a user's access."""
        shares = self._store.list_shares(workflow_id)
        target = next((s for s in shares if s.user_id == user_id), None)
        if target is None:
            return False
        self._store.delete_share(target.id)
        self._cache.get(workflow_id, {}).pop(user_id, None)
        self._persist_cache()
        return True

    def list_users(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return all users and roles for a workflow."""
        shares = self._store.list_shares(workflow_id)
        return [s.to_dict() for s in shares]

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_cache(self) -> None:
        if self._fallback_file is None:
            return
        try:
            self._fallback_file.parent.mkdir(parents=True, exist_ok=True)
            self._fallback_file.write_text(
                json.dumps({"permissions": self._cache}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Failed to persist permission cache: %s", exc)

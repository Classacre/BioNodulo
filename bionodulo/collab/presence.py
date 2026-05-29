"""Presence state manager for live collaboration sessions."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class LivePresence:
    """Server-side live session metadata for one connected collaborator."""

    workflow_id: str
    session_id: str
    user_id: str
    name: str
    color: str
    role: str
    socket: Any | None = field(default=None, repr=False)
    connected_at: float = field(default=0.0)
    updated_at: float = field(default=0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "name": self.name,
            "color": self.color,
            "role": self.role,
            "workflow_id": self.workflow_id,
            "connected_at": self.connected_at,
            "updated_at": self.updated_at,
        }


class PresenceManager:
    """Single source of truth for live collaboration sessions.

    Native Yjs sockets, REST presence endpoints, and permission kick-outs all
    read from this manager so the UI cannot drift between competing rosters.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, LivePresence]] = {}
        self._created_at: dict[str, float] = {}

    def register(
        self,
        workflow_id: str,
        presence: dict[str, Any],
        *,
        socket: Any | None = None,
    ) -> LivePresence:
        """Register or refresh one live session."""
        import time

        now = time.time()
        session_id = str(presence.get("session_id") or "")
        if not session_id:
            raise ValueError("presence session_id is required")
        room = self._sessions.setdefault(workflow_id, {})
        self._created_at.setdefault(workflow_id, datetime.now(timezone.utc).isoformat())
        session = LivePresence(
            workflow_id=workflow_id,
            session_id=session_id,
            user_id=str(presence.get("user_id") or ""),
            name=str(presence.get("name") or presence.get("user_id") or "Anonymous"),
            color=str(presence.get("color") or "#3b82f6"),
            role=str(presence.get("role") or "viewer"),
            socket=socket,
            connected_at=room.get(session_id, LivePresence(workflow_id, session_id, "", "", "", "")).connected_at or now,
            updated_at=now,
        )
        room[session_id] = session
        return session

    def unregister(self, workflow_id: str, session_id: str) -> LivePresence | None:
        """Remove one live session and clear empty rooms."""
        room = self._sessions.get(workflow_id)
        if room is None:
            return None
        removed = room.pop(session_id, None)
        if not room:
            self._sessions.pop(workflow_id, None)
            self._created_at.pop(workflow_id, None)
        return removed

    def users(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Return live sessions, optionally scoped to one workflow."""
        if workflow_id is not None:
            return [session.to_dict() for session in self._sessions.get(workflow_id, {}).values()]
        users: list[dict[str, Any]] = []
        for sessions in self._sessions.values():
            users.extend(session.to_dict() for session in sessions.values())
        return users

    def sockets_for_user(self, workflow_id: str, user_id: str) -> list[Any]:
        """Return active sockets for a user in a workflow."""
        return [
            session.socket
            for session in self._sessions.get(workflow_id, {}).values()
            if session.user_id == user_id and session.socket is not None
        ]

    def room_status(self, workflow_id: str, created_at: Any | None = None) -> dict[str, Any]:
        """Return a RoomStatusResponse-compatible live-room summary."""
        users = self.users(workflow_id)
        return {
            "workflow_id": workflow_id,
            "active": bool(users),
            "users": users,
            "created_at": created_at if created_at is not None else self._created_at.get(workflow_id),
            "client_count": len(users),
        }

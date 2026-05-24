"""WebSocket room manager for collaborative editing.

A ``Room`` tracks all connected WebSockets for a given workflow and
provides broadcast / presence primitives. ``RoomManager`` owns the map
of active rooms.

This module is retained for legacy room metadata. Native Yjs presence is
tracked by :class:`~bionodulo.collab.presence.PresenceManager`.
"""

from __future__ import annotations

import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class RoomUser:
    """Represents a connected client inside a room."""

    websocket: WebSocket
    user_id: str = ""
    user_name: str = ""
    user_color: str = "#3b82f6"
    read_only: bool = False
    client_id: int = 0
    role: str = "editor"  # owner | editor | viewer | commenter


@dataclass
class Room:
    """A single collaboration room tied to a workflow."""

    workflow_id: str = ""
    users: list[RoomUser] = field(default_factory=list)
    created_at: str = ""

    def add(self, user: RoomUser) -> None:
        """Add a client to the room if not already present."""
        if not any(u.websocket == user.websocket for u in self.users):
            self.users.append(user)

    def remove(self, websocket: WebSocket) -> RoomUser | None:
        """Remove a client and return the removed user (or None)."""
        for idx, u in enumerate(self.users):
            if u.websocket == websocket:
                return self.users.pop(idx)
        return None

    def iter_sockets(self, exclude: WebSocket | None = None) -> list[WebSocket]:
        """Return all sockets in the room, optionally excluding one."""
        return [u.websocket for u in self.users if u.websocket != exclude]

    def iter_users(self, exclude: WebSocket | None = None) -> list[RoomUser]:
        """Return all RoomUser entries, optionally excluding one websocket."""
        return [u for u in self.users if u.websocket != exclude]

    def presence_list(self) -> list[dict[str, Any]]:
        """Return JSON-serializable user presence info."""
        return [
            {
                "user_id": u.user_id,
                "user_name": u.user_name,
                "user_color": u.user_color,
                "read_only": u.read_only,
                "client_id": u.client_id,
                "role": u.role,
            }
            for u in self.users
        ]

    def is_empty(self) -> bool:
        return len(self.users) == 0


class RoomManager:
    """Manages the lifecycle of collaboration rooms.

    Each workflow ID maps to a ``Room``. The RoomManager is attached to
    ``app.state`` and accessed by both the REST routes and the WebSocket
    handler.

    Attributes:
        rooms: Mapping of ``workflow_id`` -> :class:`Room`.
    """

    def __init__(self) -> None:
        self.rooms: dict[str, Room] = {}
        self._client_counter = 0

    def _next_client_id(self) -> int:
        self._client_counter += 1
        return self._client_counter

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def join(
        self,
        workflow_id: str,
        websocket: WebSocket,
        user_id: str,
        user_name: str = "",
        user_color: str = "#3b82f6",
        read_only: bool = False,
        role: str = "editor",
    ) -> RoomUser:
        """Add a WebSocket connection to a room and broadcast a join event.

        Args:
            workflow_id: The workflow / room identifier.
            websocket: The FastAPI WebSocket connection.
            user_id: Opaque user identifier.
            user_name: Human-readable display name.
            user_color: Hex color for cursor / presence.
            read_only: Whether the user can only read (not write).
            role: Permission role of the user.

        Returns:
            The :class:`RoomUser` representing the joined client.
        """
        from datetime import datetime, timezone

        if workflow_id not in self.rooms:
            self.rooms[workflow_id] = Room(
                workflow_id=workflow_id,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        room = self.rooms[workflow_id]
        client_id = self._next_client_id()
        room_user = RoomUser(
            websocket=websocket,
            user_id=user_id,
            user_name=user_name or user_id,
            user_color=user_color,
            read_only=read_only,
            client_id=client_id,
            role=role,
        )
        room.add(room_user)

        logger.info(
            "User %s joined room %s (clients=%d, read_only=%s, role=%s)",
            user_id,
            workflow_id,
            len(room.users),
            read_only,
            role,
        )

        # Broadcast join to existing members (JSON for compatibility)
        join_msg = {
            "type": "user_joined",
            "user_id": user_id,
            "user_name": room_user.user_name,
            "user_color": room_user.user_color,
            "client_id": client_id,
            "read_only": read_only,
            "role": role,
            "active_users": room.presence_list(),
        }
        await self.broadcast(workflow_id, join_msg, exclude=websocket)
        return room_user

    async def leave(
        self,
        workflow_id: str,
        websocket: WebSocket,
    ) -> RoomUser | None:
        """Remove a WebSocket from a room and broadcast a leave event.

        Args:
            workflow_id: The workflow / room identifier.
            websocket: The FastAPI WebSocket connection to remove.

        Returns:
            The removed :class:`RoomUser`, or ``None`` if not found.
        """
        room = self.rooms.get(workflow_id)
        if room is None:
            return None

        removed = room.remove(websocket)
        if removed is None:
            return None

        logger.info(
            "User %s left room %s (clients=%d)",
            removed.user_id,
            workflow_id,
            len(room.users),
        )

        leave_msg = {
            "type": "user_left",
            "user_id": removed.user_id,
            "client_id": removed.client_id,
            "active_users": room.presence_list(),
        }
        await self.broadcast(workflow_id, leave_msg)

        # Tear down empty rooms to free memory
        if room.is_empty():
            del self.rooms[workflow_id]
            logger.info("Room %s destroyed (empty)", workflow_id)

        return removed

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def broadcast(
        self,
        workflow_id: str,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ) -> None:
        """Send a JSON message to every socket in a room.

        Args:
            workflow_id: The room to broadcast to.
            message: JSON-serializable message dict.
            exclude: Optional WebSocket to skip (typically the sender).
        """
        room = self.rooms.get(workflow_id)
        if room is None:
            return
        await self._send_to_room(room, lambda ws: ws.send_json(message), exclude=exclude)

    async def broadcast_binary(
        self,
        workflow_id: str,
        data: bytes,
        exclude: WebSocket | None = None,
    ) -> None:
        """Send a binary message to every socket in a room.

        Args:
            workflow_id: The room to broadcast to.
            data: Binary payload to send.
            exclude: Optional WebSocket to skip (typically the sender).
        """
        room = self.rooms.get(workflow_id)
        if room is None:
            return
        await self._send_to_room(room, lambda ws: ws.send_bytes(data), exclude=exclude)

    async def _send_to_room(
        self,
        room: Room,
        sender: Callable[[WebSocket], Awaitable[Any]],
        exclude: WebSocket | None = None,
    ) -> None:
        """Send to all room sockets concurrently and prune failures."""
        sockets = room.iter_sockets(exclude=exclude)
        results = await asyncio.gather(*(sender(ws) for ws in sockets), return_exceptions=True)
        dead = [ws for ws, result in zip(sockets, results) if isinstance(result, Exception)]
        for ws in dead:
            room.remove(ws)

    async def send_to(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> bool:
        """Send a JSON message to a single socket. Returns False on failure."""
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def send_binary_to(
        self,
        websocket: WebSocket,
        data: bytes,
    ) -> bool:
        """Send a binary message to a single socket. Returns False on failure."""
        try:
            await websocket.send_bytes(data)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Presence / metadata
    # ------------------------------------------------------------------

    def get_presence(self, workflow_id: str) -> list[dict[str, Any]]:
        """Return the list of active users in a room."""
        room = self.rooms.get(workflow_id)
        if room is None:
            return []
        return room.presence_list()

    def update_activity(self, workflow_id: str) -> None:
        """Bump the room's last-activity timestamp (NOP for in-memory rooms)."""
        # Future: write to CollabStore
        pass

    def room_status(self, workflow_id: str) -> dict[str, Any]:
        """Return a JSON-serializable status snapshot for a room."""
        room = self.rooms.get(workflow_id)
        if room is None:
            return {
                "workflow_id": workflow_id,
                "active": False,
                "users": [],
                "created_at": None,
            }
        return {
            "workflow_id": workflow_id,
            "active": True,
            "users": room.presence_list(),
            "created_at": room.created_at,
            "client_count": len(room.users),
        }

    def get_user_count(self, workflow_id: str) -> int:
        """Return the number of connected clients in a room."""
        room = self.rooms.get(workflow_id)
        if room is None:
            return 0
        return len(room.users)

    def get_user_by_websocket(
        self, workflow_id: str, websocket: WebSocket
    ) -> RoomUser | None:
        """Return the RoomUser associated with a websocket in a room."""
        room = self.rooms.get(workflow_id)
        if room is None:
            return None
        for u in room.users:
            if u.websocket == websocket:
                return u
        return None

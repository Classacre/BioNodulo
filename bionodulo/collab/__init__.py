"""Collaborative editing package for BioNodulo.

Exports the main classes used by the server to manage real-time
multiplayer workflow editing sessions.
"""

from __future__ import annotations

from bionodulo.collab.permissions import PermissionChecker
from bionodulo.collab.presence import PresenceManager
from bionodulo.collab.room_manager import RoomManager

__all__ = [
    "RoomManager",
    "PresenceManager",
    "PermissionChecker",
]

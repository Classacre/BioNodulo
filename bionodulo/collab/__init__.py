"""Collaborative editing package for BioNodulo.

Exports the main classes used by the server to manage real-time
multiplayer workflow editing sessions.
"""

from __future__ import annotations

from bionodulo.collab.room_manager import RoomManager
from bionodulo.collab.presence import AwarenessManager
from bionodulo.collab.permissions import PermissionChecker

__all__ = [
    "RoomManager",
    "AwarenessManager",
    "PermissionChecker",
]

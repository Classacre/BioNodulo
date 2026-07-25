"""Focused registered node for ``aldex2``."""

from .adapter import ALDEx2Node as _NodeContract


class ALDEx2Node(_NodeContract):
    NODE_ID = "aldex2"

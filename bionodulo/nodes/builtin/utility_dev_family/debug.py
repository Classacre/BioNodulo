"""Stable owner for the ``debug`` node."""

from .adapter import _DebugContract


class DebugNode(_DebugContract):
    NODE_ID = "debug"
    UPSTREAM_SYMBOL = "DebugNode"

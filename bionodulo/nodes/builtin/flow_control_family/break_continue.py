"""Stable owner for the ``break_continue`` node."""

from .adapter import _BreakContinueContract


class BreakContinueNode(_BreakContinueContract):
    """Emit an explicit conditional loop-control signal."""

    NODE_ID = "break_continue"
    UPSTREAM_SYMBOL = "BreakContinueNode"

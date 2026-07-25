"""Stable owner for the ``breakpoint`` node."""

from .adapter import _BreakpointContract


class BreakpointNode(_BreakpointContract):
    NODE_ID = "breakpoint"
    UPSTREAM_SYMBOL = "BreakpointNode"

"""Stable owner for the ``gate`` node."""

from .adapter import _GateContract


class GateNode(_GateContract):
    """Pass, default, skip, or halt after a validated condition."""

    NODE_ID = "gate"
    UPSTREAM_SYMBOL = "GateNode"

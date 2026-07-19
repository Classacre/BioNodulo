"""Stable owner for the ``foreach`` node."""

from .adapter import _ForEachContract


class ForEachNode(_ForEachContract):
    """Declare bounded sequential loop-body iteration."""

    NODE_ID = "foreach"
    UPSTREAM_SYMBOL = "ForEachNode"

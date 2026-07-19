"""Stable owner for the ``merge`` node."""

from .adapter import _MergeContract


class MergeNode(_MergeContract):
    """Gather multiple inputs with an explicit merge strategy."""

    NODE_ID = "merge"
    UPSTREAM_SYMBOL = "MergeNode"

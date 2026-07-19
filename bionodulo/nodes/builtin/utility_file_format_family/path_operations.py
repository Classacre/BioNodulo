"""Stable owner for the ``path_operations`` node."""

from .adapter import _PathOperationsContract


class PathOperationsNode(_PathOperationsContract):
    NODE_ID = "path_operations"
    UPSTREAM_SYMBOL = "PathOperationsNode"

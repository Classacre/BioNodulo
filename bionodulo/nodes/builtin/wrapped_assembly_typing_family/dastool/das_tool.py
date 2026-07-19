"""Stable owner for ``das_tool``."""

from .adapter import _DASToolContract


class DASToolNode(_DASToolContract):
    NODE_ID = "das_tool"
    UPSTREAM_SYMBOL = "DASToolNode"

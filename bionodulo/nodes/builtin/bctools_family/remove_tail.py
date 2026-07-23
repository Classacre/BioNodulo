"""Focused owner for ``bctools_remove_tail``."""

from .adapter import _BctoolsRemoveTailContract


class BctoolsRemoveTailNode(_BctoolsRemoveTailContract):
    NODE_ID = "bctools_remove_tail"
    UPSTREAM_SYMBOL = "BctoolsRemoveTailNode"

"""Stable owner for the ``select_from_list`` node."""

from .adapter import _SelectFromListContract


class SelectFromListNode(_SelectFromListContract):
    NODE_ID = "select_from_list"
    UPSTREAM_SYMBOL = "SelectFromListNode"

"""Stable owner for the ``list_operations`` node."""

from .adapter import _ListOperationsContract


class ListOperationsNode(_ListOperationsContract):
    NODE_ID = "list_operations"
    UPSTREAM_SYMBOL = "ListOperationsNode"

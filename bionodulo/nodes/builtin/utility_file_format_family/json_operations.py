"""Stable owner for the ``json_operations`` node."""

from .adapter import _JSONOperationsContract


class JSONOperationsNode(_JSONOperationsContract):
    NODE_ID = "json_operations"
    UPSTREAM_SYMBOL = "JSONOperationsNode"

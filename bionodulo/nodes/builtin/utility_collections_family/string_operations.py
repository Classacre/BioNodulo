"""Stable owner for the ``string_operations`` node."""

from .adapter import _StringOperationsContract


class StringOperationsNode(_StringOperationsContract):
    NODE_ID = "string_operations"
    UPSTREAM_SYMBOL = "StringOperationsNode"

"""Stable owner for the ``flatten_nested`` node."""

from .adapter import _FlattenNestedContract


class FlattenNestedNode(_FlattenNestedContract):
    NODE_ID = "flatten_nested"
    UPSTREAM_SYMBOL = "FlattenNestedNode"

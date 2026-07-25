"""Focused owner for ``graphlan``."""

from .adapter import GraphlanNode as _NodeContract


class GraphlanNode(_NodeContract):
    NODE_ID = "graphlan"
    UPSTREAM_SYMBOL = "GraphlanNode"

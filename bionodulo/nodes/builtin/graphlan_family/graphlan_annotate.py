"""Focused owner for ``graphlan_annotate``."""

from .adapter import GraphlanAnnotateNode as _NodeContract


class GraphlanAnnotateNode(_NodeContract):
    NODE_ID = "graphlan_annotate"
    UPSTREAM_SYMBOL = "GraphlanAnnotateNode"

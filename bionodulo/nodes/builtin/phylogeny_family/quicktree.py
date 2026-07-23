"""Focused owner for ``quicktree``."""

from .classic_adapter import QuicktreeNode as _NodeContract


class QuicktreeNode(_NodeContract):
    NODE_ID = "quicktree"

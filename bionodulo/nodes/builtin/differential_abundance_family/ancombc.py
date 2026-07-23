"""Focused registered node for ``ancombc``."""

from .adapter import ANCOMBCNode as _NodeContract


class ANCOMBCNode(_NodeContract):
    NODE_ID = "ancombc"

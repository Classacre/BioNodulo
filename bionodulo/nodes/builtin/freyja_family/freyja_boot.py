"""Focused owner for ``freyja_boot``."""

from .adapter import FreyjaBootNode as _NodeContract


class FreyjaBootNode(_NodeContract):
    NODE_ID = "freyja_boot"
    UPSTREAM_SYMBOL = "FreyjaBootNode"

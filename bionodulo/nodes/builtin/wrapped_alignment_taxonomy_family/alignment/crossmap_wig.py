"""Stable owner for ``crossmap_wig``."""

from .adapter import _CrossMapWigContract


class CrossMapWigNode(_CrossMapWigContract):
    NODE_ID = "crossmap_wig"
    UPSTREAM_SYMBOL = "CrossMapWigNode"

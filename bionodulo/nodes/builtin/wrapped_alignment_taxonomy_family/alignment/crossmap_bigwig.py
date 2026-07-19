"""Stable owner for ``crossmap_bw``."""

from .adapter import _CrossMapBigWigContract


class CrossMapBigWigNode(_CrossMapBigWigContract):
    NODE_ID = "crossmap_bw"
    UPSTREAM_SYMBOL = "CrossMapBigWigNode"

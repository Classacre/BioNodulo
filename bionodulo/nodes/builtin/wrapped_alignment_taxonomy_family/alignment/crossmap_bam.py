"""Stable owner for ``crossmap_bam``."""

from .adapter import _CrossMapBamContract


class CrossMapBamNode(_CrossMapBamContract):
    NODE_ID = "crossmap_bam"
    UPSTREAM_SYMBOL = "CrossMapBamNode"

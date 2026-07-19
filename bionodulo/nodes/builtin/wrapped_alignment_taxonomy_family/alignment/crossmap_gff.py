"""Stable owner for ``crossmap_gff``."""

from .adapter import _CrossMapGffContract


class CrossMapGffNode(_CrossMapGffContract):
    NODE_ID = "crossmap_gff"
    UPSTREAM_SYMBOL = "CrossMapGffNode"

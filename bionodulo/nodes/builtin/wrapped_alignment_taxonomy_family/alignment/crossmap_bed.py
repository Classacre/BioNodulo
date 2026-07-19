"""Stable owner for ``crossmap_bed``."""

from .adapter import _CrossMapBedContract


class CrossMapBedNode(_CrossMapBedContract):
    NODE_ID = "crossmap_bed"
    UPSTREAM_SYMBOL = "CrossMapBedNode"

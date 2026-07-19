"""Stable owner for ``crossmap_region``."""

from .adapter import _CrossMapRegionContract


class CrossMapRegionNode(_CrossMapRegionContract):
    NODE_ID = "crossmap_region"
    UPSTREAM_SYMBOL = "CrossMapRegionNode"

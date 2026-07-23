"""Focused owner for ``crossmap_region``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapRegionContract


class CrossMapRegionNode(_CrossMapRegionContract):
    NODE_ID = "crossmap_region"
    UPSTREAM_SYMBOL = "CrossMapRegionNode"

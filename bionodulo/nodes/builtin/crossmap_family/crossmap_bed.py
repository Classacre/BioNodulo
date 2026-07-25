"""Focused owner for ``crossmap_bed``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapBedContract


class CrossMapBedNode(_CrossMapBedContract):
    NODE_ID = "crossmap_bed"
    UPSTREAM_SYMBOL = "CrossMapBedNode"

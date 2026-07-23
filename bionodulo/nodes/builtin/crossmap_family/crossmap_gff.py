"""Focused owner for ``crossmap_gff``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapGffContract


class CrossMapGffNode(_CrossMapGffContract):
    NODE_ID = "crossmap_gff"
    UPSTREAM_SYMBOL = "CrossMapGffNode"

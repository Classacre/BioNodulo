"""Focused owner for ``crossmap_wig``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapWigContract


class CrossMapWigNode(_CrossMapWigContract):
    NODE_ID = "crossmap_wig"
    UPSTREAM_SYMBOL = "CrossMapWigNode"

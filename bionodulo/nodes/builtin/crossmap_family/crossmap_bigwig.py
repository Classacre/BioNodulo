"""Focused owner for ``crossmap_bw``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapBigWigContract


class CrossMapBigWigNode(_CrossMapBigWigContract):
    NODE_ID = "crossmap_bw"
    UPSTREAM_SYMBOL = "CrossMapBigWigNode"

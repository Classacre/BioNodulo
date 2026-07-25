"""Focused owner for ``crossmap_bam``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapBamContract


class CrossMapBamNode(_CrossMapBamContract):
    NODE_ID = "crossmap_bam"
    UPSTREAM_SYMBOL = "CrossMapBamNode"

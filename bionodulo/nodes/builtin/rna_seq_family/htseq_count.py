"""Focused owner for ``htseq_count``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _HTSeqCountContract


class HTSeqCountNode(_HTSeqCountContract):
    NODE_ID = "htseq_count"

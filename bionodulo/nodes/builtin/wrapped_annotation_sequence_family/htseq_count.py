"""Stable owner for ``htseq_count``."""

from .legacy import _HTSeqCountContract


class HTSeqCountNode(_HTSeqCountContract):
    NODE_ID = "htseq_count"

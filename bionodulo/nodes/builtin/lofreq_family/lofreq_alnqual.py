"""Focused owner for ``lofreq_alnqual``."""

from .adapter import LoFreqAlnQualNode as _NodeContract


class LoFreqAlnQualNode(_NodeContract):
    NODE_ID = "lofreq_alnqual"
    UPSTREAM_SYMBOL = "LoFreqAlnQualNode"

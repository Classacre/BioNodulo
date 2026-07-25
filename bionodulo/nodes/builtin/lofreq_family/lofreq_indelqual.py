"""Focused owner for ``lofreq_indelqual``."""

from .adapter import LoFreqIndelQualNode as _NodeContract


class LoFreqIndelQualNode(_NodeContract):
    NODE_ID = "lofreq_indelqual"
    UPSTREAM_SYMBOL = "LoFreqIndelQualNode"

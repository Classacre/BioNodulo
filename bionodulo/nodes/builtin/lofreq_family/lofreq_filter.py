"""Focused owner for ``lofreq_filter``."""

from .adapter import LoFreqFilterNode as _NodeContract


class LoFreqFilterNode(_NodeContract):
    NODE_ID = "lofreq_filter"
    UPSTREAM_SYMBOL = "LoFreqFilterNode"

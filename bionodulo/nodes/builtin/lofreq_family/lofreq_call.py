"""Focused owner for ``lofreq_call``."""

from .adapter import LoFreqCallNode as _NodeContract


class LoFreqCallNode(_NodeContract):
    NODE_ID = "lofreq_call"
    UPSTREAM_SYMBOL = "LoFreqCallNode"

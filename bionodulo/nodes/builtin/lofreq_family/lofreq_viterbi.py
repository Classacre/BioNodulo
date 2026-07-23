"""Focused owner for ``lofreq_viterbi``."""

from .adapter import LoFreqViterbiNode as _NodeContract


class LoFreqViterbiNode(_NodeContract):
    NODE_ID = "lofreq_viterbi"
    UPSTREAM_SYMBOL = "LoFreqViterbiNode"

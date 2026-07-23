"""Focused owner for ``preseq_lc_extrap``."""

from .adapter import PreseqLCExtrapNode as _NodeContract


class PreseqLCExtrapNode(_NodeContract):
    NODE_ID = "preseq_lc_extrap"
    UPSTREAM_SYMBOL = "PreseqLCExtrapNode"

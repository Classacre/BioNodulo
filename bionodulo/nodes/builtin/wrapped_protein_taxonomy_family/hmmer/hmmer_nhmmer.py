"""Stable owner for ``hmmer_nhmmer``."""

from .adapter import _HMMERNhmmerContract


class HMMERNhmmerNode(_HMMERNhmmerContract):
    NODE_ID = "hmmer_nhmmer"
    UPSTREAM_SYMBOL = "HMMERNhmmerNode"

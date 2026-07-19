"""Stable owner for ``hmmer_jackhmmer``."""

from .adapter import _HMMERJackhmmerContract


class HMMERJackhmmerNode(_HMMERJackhmmerContract):
    NODE_ID = "hmmer_jackhmmer"
    UPSTREAM_SYMBOL = "HMMERJackhmmerNode"

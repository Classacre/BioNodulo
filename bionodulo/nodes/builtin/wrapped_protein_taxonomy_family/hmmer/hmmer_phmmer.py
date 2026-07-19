"""Stable owner for ``hmmer_phmmer``."""

from .adapter import _HMMERPhmmerContract


class HMMERPhmmerNode(_HMMERPhmmerContract):
    NODE_ID = "hmmer_phmmer"
    UPSTREAM_SYMBOL = "HMMERPhmmerNode"

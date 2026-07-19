"""Stable owner for ``hmmer_hmmemit``."""

from .adapter import _HMMERHmmemitContract


class HMMERHmmemitNode(_HMMERHmmemitContract):
    NODE_ID = "hmmer_hmmemit"
    UPSTREAM_SYMBOL = "HMMERHmmemitNode"

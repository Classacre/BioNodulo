"""Stable owner for ``hmmer_hmmconvert``."""

from .adapter import _HMMERHmmconvertContract


class HMMERHmmconvertNode(_HMMERHmmconvertContract):
    NODE_ID = "hmmer_hmmconvert"
    UPSTREAM_SYMBOL = "HMMERHmmconvertNode"

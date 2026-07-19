"""Stable owner for ``hmmer_hmmalign``."""

from .adapter import _HMMERHmmalignContract


class HMMERHmmalignNode(_HMMERHmmalignContract):
    NODE_ID = "hmmer_hmmalign"
    UPSTREAM_SYMBOL = "HMMERHmmalignNode"

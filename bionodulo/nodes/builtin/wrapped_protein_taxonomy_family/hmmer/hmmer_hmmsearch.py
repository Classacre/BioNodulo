"""Stable owner for ``hmmer_hmmsearch``."""

from .adapter import _HMMERHmmsearchContract


class HMMERHmmsearchNode(_HMMERHmmsearchContract):
    NODE_ID = "hmmer_hmmsearch"
    UPSTREAM_SYMBOL = "HMMERHmmsearchNode"

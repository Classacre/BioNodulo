"""Stable owner for ``hmmer_hmmscan``."""

from .adapter import _HMMERHmmscanContract


class HMMERHmmscanNode(_HMMERHmmscanContract):
    NODE_ID = "hmmer_hmmscan"
    UPSTREAM_SYMBOL = "HMMERHmmscanNode"

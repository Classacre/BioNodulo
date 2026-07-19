"""Stable owner for ``hmmer_nhmmscan``."""

from .adapter import _HMMERNhmmscanContract


class HMMERNhmmscanNode(_HMMERNhmmscanContract):
    NODE_ID = "hmmer_nhmmscan"
    UPSTREAM_SYMBOL = "HMMERNhmmscanNode"

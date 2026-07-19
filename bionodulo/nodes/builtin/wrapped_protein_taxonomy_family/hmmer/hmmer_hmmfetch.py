"""Stable owner for ``hmmer_hmmfetch``."""

from .adapter import _HMMERHmmfetchContract


class HMMERHmmfetchNode(_HMMERHmmfetchContract):
    NODE_ID = "hmmer_hmmfetch"
    UPSTREAM_SYMBOL = "HMMERHmmfetchNode"

"""Stable owner for ``hmmer_alimask``."""

from .adapter import _HMMERAlimaskContract


class HMMERAlimaskNode(_HMMERAlimaskContract):
    NODE_ID = "hmmer_alimask"
    UPSTREAM_SYMBOL = "HMMERAlimaskNode"

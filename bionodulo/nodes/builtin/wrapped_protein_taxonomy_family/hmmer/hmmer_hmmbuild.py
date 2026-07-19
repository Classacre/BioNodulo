"""Stable owner for ``hmmer_hmmbuild``."""

from .adapter import _HMMERHmmbuildContract


class HMMERHmmbuildNode(_HMMERHmmbuildContract):
    NODE_ID = "hmmer_hmmbuild"
    UPSTREAM_SYMBOL = "HMMERHmmbuildNode"

"""Stable owner for ``est_abundance``."""

from .adapter import _BrackenEstAbundanceContract


class BrackenEstAbundanceNode(_BrackenEstAbundanceContract):
    NODE_ID = "est_abundance"
    UPSTREAM_SYMBOL = "BrackenEstAbundanceNode"

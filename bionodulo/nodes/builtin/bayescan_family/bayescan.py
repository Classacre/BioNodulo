"""Focused owner for ``bayescan``."""

from .adapter import BayeScanNode as _NodeContract


class BayeScanNode(_NodeContract):
    NODE_ID = "bayescan"
    UPSTREAM_SYMBOL = "BayeScanNode"

"""Stable owner for ``hybpiper``."""

from .adapter import _HybPiperContract


class HybPiperNode(_HybPiperContract):
    NODE_ID = "hybpiper"
    UPSTREAM_SYMBOL = "HybPiperNode"

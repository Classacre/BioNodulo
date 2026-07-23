"""Stable owner for ``bg_diamond``."""

from .adapter import _GalaxyDiamondContract


class GalaxyDiamondNode(_GalaxyDiamondContract):
    NODE_ID = "bg_diamond"
    UPSTREAM_SYMBOL = "GalaxyDiamondNode"

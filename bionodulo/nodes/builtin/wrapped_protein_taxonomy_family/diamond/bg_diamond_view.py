"""Stable owner for ``bg_diamond_view``."""

from .adapter import _GalaxyDiamondViewContract


class GalaxyDiamondViewNode(_GalaxyDiamondViewContract):
    NODE_ID = "bg_diamond_view"
    UPSTREAM_SYMBOL = "GalaxyDiamondViewNode"

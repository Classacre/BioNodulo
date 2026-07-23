"""Stable owner for ``bg_diamond_makedb``."""

from .adapter import _GalaxyDiamondMakeDBContract


class GalaxyDiamondMakeDBNode(_GalaxyDiamondMakeDBContract):
    NODE_ID = "bg_diamond_makedb"
    UPSTREAM_SYMBOL = "GalaxyDiamondMakeDBNode"

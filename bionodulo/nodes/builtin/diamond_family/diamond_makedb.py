"""Stable owner for ``diamond_makedb``."""

from .adapter import _DiamondMakeDBContract


class DiamondMakeDBNode(_DiamondMakeDBContract):
    NODE_ID = "diamond_makedb"
    UPSTREAM_SYMBOL = "DiamondMakeDBNode"

"""Stable owner for ``diamond_align``."""

from .adapter import _DiamondAlignContract


class DiamondAlignNode(_DiamondAlignContract):
    NODE_ID = "diamond_align"
    UPSTREAM_SYMBOL = "DiamondAlignNode"

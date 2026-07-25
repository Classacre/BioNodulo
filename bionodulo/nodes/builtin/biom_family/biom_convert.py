"""Stable owner for ``biom_convert``."""

from .adapter import _BiomConvertContract


class BiomConvertNode(_BiomConvertContract):
    NODE_ID = "biom_convert"
    UPSTREAM_SYMBOL = "BiomConvertNode"

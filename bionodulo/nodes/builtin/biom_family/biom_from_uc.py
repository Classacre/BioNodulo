"""Stable owner for ``biom_from_uc``."""

from .adapter import _BiomFromUcContract


class BiomFromUcNode(_BiomFromUcContract):
    NODE_ID = "biom_from_uc"
    UPSTREAM_SYMBOL = "BiomFromUcNode"

"""Stable owner for ``biom_normalize_table``."""

from .adapter import _BiomNormalizeTableContract


class BiomNormalizeTableNode(_BiomNormalizeTableContract):
    NODE_ID = "biom_normalize_table"
    UPSTREAM_SYMBOL = "BiomNormalizeTableNode"

"""Stable owner for ``biom_subset_table``."""

from .adapter import _BiomSubsetTableContract


class BiomSubsetTableNode(_BiomSubsetTableContract):
    NODE_ID = "biom_subset_table"
    UPSTREAM_SYMBOL = "BiomSubsetTableNode"

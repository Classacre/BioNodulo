"""Stable owner for ``biom_summarize_table``."""

from .adapter import _BiomSummarizeTableContract


class BiomSummarizeTableNode(_BiomSummarizeTableContract):
    NODE_ID = "biom_summarize_table"
    UPSTREAM_SYMBOL = "BiomSummarizeTableNode"

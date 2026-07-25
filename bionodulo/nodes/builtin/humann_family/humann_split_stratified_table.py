"""Stable owner for ``humann_split_stratified_table``."""

from .adapter import _HUMAnNSplitStratifiedTableContract


class HUMAnNSplitStratifiedTableNode(_HUMAnNSplitStratifiedTableContract):
    NODE_ID = "humann_split_stratified_table"
    UPSTREAM_SYMBOL = "HUMAnNSplitStratifiedTableNode"

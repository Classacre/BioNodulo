"""Stable owner for ``humann_split_table``."""

from .adapter import _HUMAnNSplitTableContract


class HUMAnNSplitTableNode(_HUMAnNSplitTableContract):
    NODE_ID = "humann_split_table"
    UPSTREAM_SYMBOL = "HUMAnNSplitTableNode"

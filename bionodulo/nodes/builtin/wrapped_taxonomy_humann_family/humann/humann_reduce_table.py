"""Stable owner for ``humann_reduce_table``."""

from .adapter import _HUMAnNReduceTableContract


class HUMAnNReduceTableNode(_HUMAnNReduceTableContract):
    NODE_ID = "humann_reduce_table"
    UPSTREAM_SYMBOL = "HUMAnNReduceTableNode"

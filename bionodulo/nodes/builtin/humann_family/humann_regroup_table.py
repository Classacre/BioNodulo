"""Stable owner for ``humann_regroup_table``."""

from .adapter import _HUMAnNRegroupTableContract


class HUMAnNRegroupTableNode(_HUMAnNRegroupTableContract):
    NODE_ID = "humann_regroup_table"
    UPSTREAM_SYMBOL = "HUMAnNRegroupTableNode"

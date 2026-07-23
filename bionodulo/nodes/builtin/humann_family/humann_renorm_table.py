"""Stable owner for ``humann_renorm_table``."""

from .adapter import _HUMAnNRenormTableContract


class HUMAnNRenormTableNode(_HUMAnNRenormTableContract):
    NODE_ID = "humann_renorm_table"
    UPSTREAM_SYMBOL = "HUMAnNRenormTableNode"

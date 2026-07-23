"""Stable owner for ``humann_rename_table``."""

from .adapter import _HUMAnNRenameTableContract


class HUMAnNRenameTableNode(_HUMAnNRenameTableContract):
    NODE_ID = "humann_rename_table"
    UPSTREAM_SYMBOL = "HUMAnNRenameTableNode"

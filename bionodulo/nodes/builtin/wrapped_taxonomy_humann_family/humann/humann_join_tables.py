"""Stable owner for ``humann_join_tables``."""

from .adapter import _HUMAnNJoinTablesContract


class HUMAnNJoinTablesNode(_HUMAnNJoinTablesContract):
    NODE_ID = "humann_join_tables"
    UPSTREAM_SYMBOL = "HUMAnNJoinTablesNode"

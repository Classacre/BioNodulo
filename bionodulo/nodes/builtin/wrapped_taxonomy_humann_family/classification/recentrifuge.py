"""Stable owner for ``recentrifuge``."""

from .adapter import _RecentrifugeContract


class RecentrifugeNode(_RecentrifugeContract):
    NODE_ID = "recentrifuge"
    UPSTREAM_SYMBOL = "RecentrifugeNode"

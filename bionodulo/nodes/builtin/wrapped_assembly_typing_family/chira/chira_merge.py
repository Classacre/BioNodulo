"""Stable owner for ``chira_merge``."""

from .adapter import _ChiraMergeContract


class ChiraMergeNode(_ChiraMergeContract):
    NODE_ID = "chira_merge"
    UPSTREAM_SYMBOL = "ChiraMergeNode"

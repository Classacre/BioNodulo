"""Focused owner for ``chira_map``."""

from .adapter import _ChiraMapContract


class ChiraMapNode(_ChiraMapContract):
    NODE_ID = "chira_map"
    UPSTREAM_SYMBOL = "ChiraMapNode"

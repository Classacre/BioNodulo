"""Focused owner for ``chira_quantify``."""

from .adapter import _ChiraQuantifyContract


class ChiraQuantifyNode(_ChiraQuantifyContract):
    NODE_ID = "chira_quantify"
    UPSTREAM_SYMBOL = "ChiraQuantifyNode"

"""Focused owner for ``chira_collapse``."""

from .adapter import _ChiraCollapseContract


class ChiraCollapseNode(_ChiraCollapseContract):
    NODE_ID = "chira_collapse"
    UPSTREAM_SYMBOL = "ChiraCollapseNode"

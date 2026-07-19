"""Stable owner for ``chira_extract``."""

from .adapter import _ChiraExtractContract


class ChiraExtractNode(_ChiraExtractContract):
    NODE_ID = "chira_extract"
    UPSTREAM_SYMBOL = "ChiraExtractNode"

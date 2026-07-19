"""Stable owner for ``cat_summarise``."""

from .adapter import _CatSummariseContract


class CatSummariseNode(_CatSummariseContract):
    NODE_ID = "cat_summarise"
    UPSTREAM_SYMBOL = "CatSummariseNode"

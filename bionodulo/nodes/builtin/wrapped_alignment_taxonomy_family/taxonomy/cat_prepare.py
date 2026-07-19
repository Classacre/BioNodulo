"""Stable owner for ``cat_prepare``."""

from .adapter import _CatPrepareContract


class CatPrepareNode(_CatPrepareContract):
    NODE_ID = "cat_prepare"
    UPSTREAM_SYMBOL = "CatPrepareNode"

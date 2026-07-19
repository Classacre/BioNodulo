"""Stable owner for ``cat_bins``."""

from .adapter import _CatBinsContract


class CatBinsNode(_CatBinsContract):
    NODE_ID = "cat_bins"
    UPSTREAM_SYMBOL = "CatBinsNode"

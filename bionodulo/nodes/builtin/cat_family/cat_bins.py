"""Focused owner for ``cat_bins``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CatBinsContract


class CatBinsNode(_CatBinsContract):
    NODE_ID = "cat_bins"
    UPSTREAM_SYMBOL = "CatBinsNode"

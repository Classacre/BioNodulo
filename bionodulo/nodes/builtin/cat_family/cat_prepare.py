"""Focused owner for ``cat_prepare``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CatPrepareContract


class CatPrepareNode(_CatPrepareContract):
    NODE_ID = "cat_prepare"
    UPSTREAM_SYMBOL = "CatPrepareNode"

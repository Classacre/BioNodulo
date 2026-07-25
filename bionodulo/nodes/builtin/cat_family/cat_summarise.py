"""Focused owner for ``cat_summarise``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CatSummariseContract


class CatSummariseNode(_CatSummariseContract):
    NODE_ID = "cat_summarise"
    UPSTREAM_SYMBOL = "CatSummariseNode"

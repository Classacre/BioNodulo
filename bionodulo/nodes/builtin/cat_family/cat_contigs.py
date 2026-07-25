"""Focused owner for ``cat_contigs``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CatContigsContract


class CatContigsNode(_CatContigsContract):
    NODE_ID = "cat_contigs"
    UPSTREAM_SYMBOL = "CatContigsNode"

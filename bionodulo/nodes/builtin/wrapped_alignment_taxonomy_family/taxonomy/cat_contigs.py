"""Stable owner for ``cat_contigs``."""

from .adapter import _CatContigsContract


class CatContigsNode(_CatContigsContract):
    NODE_ID = "cat_contigs"
    UPSTREAM_SYMBOL = "CatContigsNode"

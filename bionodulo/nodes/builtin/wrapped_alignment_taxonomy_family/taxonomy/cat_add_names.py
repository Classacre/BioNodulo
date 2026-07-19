"""Stable owner for ``cat_add_names``."""

from .adapter import _CatAddNamesContract


class CatAddNamesNode(_CatAddNamesContract):
    NODE_ID = "cat_add_names"
    UPSTREAM_SYMBOL = "CatAddNamesNode"

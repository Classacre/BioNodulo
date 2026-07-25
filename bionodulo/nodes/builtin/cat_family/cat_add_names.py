"""Focused owner for ``cat_add_names``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CatAddNamesContract


class CatAddNamesNode(_CatAddNamesContract):
    NODE_ID = "cat_add_names"
    UPSTREAM_SYMBOL = "CatAddNamesNode"

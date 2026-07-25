"""Focused owner for ``cawlign``."""

from bionodulo.nodes.builtin._alignment_taxonomy_taxonomy_adapter import _CawlignContract


class CawlignNode(_CawlignContract):
    NODE_ID = "cawlign"
    UPSTREAM_SYMBOL = "CawlignNode"

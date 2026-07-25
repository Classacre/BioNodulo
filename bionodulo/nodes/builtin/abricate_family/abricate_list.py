"""Focused owner for ``abricate_list``."""

from .adapter import _ABRicateListContract


class ABRicateListNode(_ABRicateListContract):
    NODE_ID = "abricate_list"
    UPSTREAM_SYMBOL = "ABRicateListNode"

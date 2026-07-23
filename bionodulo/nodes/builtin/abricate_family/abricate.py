"""Focused owner for ``abricate``."""

from .adapter import _ABRicateContract


class ABRicateNode(_ABRicateContract):
    NODE_ID = "abricate"
    UPSTREAM_SYMBOL = "ABRicateNode"

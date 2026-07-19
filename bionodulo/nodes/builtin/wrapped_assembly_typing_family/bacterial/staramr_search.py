"""Stable owner for ``staramr_search``."""

from .typing_adapter import _StaramrSearchContract


class StaramrSearchNode(_StaramrSearchContract):
    NODE_ID = "staramr_search"
    UPSTREAM_SYMBOL = "StaramrSearchNode"

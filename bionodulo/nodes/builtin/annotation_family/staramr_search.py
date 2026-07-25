"""Focused owner for ``staramr_search``."""

from bionodulo.nodes.builtin._bacterial_typing_adapter import _StaramrSearchContract


class StaramrSearchNode(_StaramrSearchContract):
    NODE_ID = "staramr_search"
    UPSTREAM_SYMBOL = "StaramrSearchNode"

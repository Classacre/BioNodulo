"""Focused owner for ``bioext_bealign``."""

from .adapter import BioExtBealignNode as _NodeContract


class BioExtBealignNode(_NodeContract):
    NODE_ID = "bioext_bealign"
    UPSTREAM_SYMBOL = "BioExtBealignNode"

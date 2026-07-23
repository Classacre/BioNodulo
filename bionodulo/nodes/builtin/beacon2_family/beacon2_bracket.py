"""Stable owner for ``beacon2_bracket``."""

from .adapter import _Beacon2BracketContract


class Beacon2BracketNode(_Beacon2BracketContract):
    NODE_ID = "beacon2_bracket"
    UPSTREAM_SYMBOL = "Beacon2BracketNode"

"""Stable owner for ``cawlign``."""

from .adapter import _CawlignContract


class CawlignNode(_CawlignContract):
    NODE_ID = "cawlign"
    UPSTREAM_SYMBOL = "CawlignNode"

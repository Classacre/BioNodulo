"""Stable owner for ``centrifuge``."""

from .adapter import _CentrifugeContract


class CentrifugeNode(_CentrifugeContract):
    NODE_ID = "centrifuge"
    UPSTREAM_SYMBOL = "CentrifugeNode"

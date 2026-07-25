"""Stable owner for ``kaiju``."""

from .adapter import _KaijuContract


class KaijuNode(_KaijuContract):
    NODE_ID = "kaiju"
    UPSTREAM_SYMBOL = "KaijuNode"

"""Stable owner for ``kleborate``."""

from .typing_adapter import _KleborateContract


class KleborateNode(_KleborateContract):
    NODE_ID = "kleborate"
    UPSTREAM_SYMBOL = "KleborateNode"

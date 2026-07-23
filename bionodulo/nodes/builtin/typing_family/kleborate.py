"""Focused owner for ``kleborate``."""

from bionodulo.nodes.builtin._bacterial_typing_adapter import _KleborateContract


class KleborateNode(_KleborateContract):
    NODE_ID = "kleborate"
    UPSTREAM_SYMBOL = "KleborateNode"

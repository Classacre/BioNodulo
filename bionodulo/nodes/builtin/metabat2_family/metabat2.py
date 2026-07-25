"""Focused owner for ``metabat2``."""

from .adapter import MetaBAT2Node as _NodeContract


class MetaBAT2Node(_NodeContract):
    NODE_ID = "metabat2"
    UPSTREAM_SYMBOL = "MetaBAT2Node"

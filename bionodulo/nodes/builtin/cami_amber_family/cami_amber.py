"""Focused owner for ``cami_amber``."""

from .adapter import CamiAmberNode as _NodeContract


class CamiAmberNode(_NodeContract):
    NODE_ID = "cami_amber"
    UPSTREAM_SYMBOL = "CamiAmberNode"

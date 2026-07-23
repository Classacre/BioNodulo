"""Focused owner for ``cami_amber_add``."""

from .adapter import CamiAmberAddNode as _NodeContract


class CamiAmberAddNode(_NodeContract):
    NODE_ID = "cami_amber_add"
    UPSTREAM_SYMBOL = "CamiAmberAddNode"

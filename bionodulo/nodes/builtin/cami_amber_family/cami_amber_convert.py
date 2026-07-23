"""Focused owner for ``cami_amber_convert``."""

from .adapter import CamiAmberConvertNode as _NodeContract


class CamiAmberConvertNode(_NodeContract):
    NODE_ID = "cami_amber_convert"
    UPSTREAM_SYMBOL = "CamiAmberConvertNode"

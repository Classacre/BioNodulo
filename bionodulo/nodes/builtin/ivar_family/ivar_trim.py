"""Focused owner for ``ivar_trim``."""

from .adapter import IVarTrimNode as _NodeContract


class IVarTrimNode(_NodeContract):
    NODE_ID = "ivar_trim"
    UPSTREAM_SYMBOL = "IVarTrimNode"

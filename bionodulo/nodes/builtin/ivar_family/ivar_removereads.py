"""Focused owner for ``ivar_removereads``."""

from .adapter import IVarRemoveReadsNode as _NodeContract


class IVarRemoveReadsNode(_NodeContract):
    NODE_ID = "ivar_removereads"
    UPSTREAM_SYMBOL = "IVarRemoveReadsNode"

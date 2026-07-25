"""Focused owner for ``ivar_variants``."""

from .adapter import IVarVariantsNode as _NodeContract


class IVarVariantsNode(_NodeContract):
    NODE_ID = "ivar_variants"
    UPSTREAM_SYMBOL = "IVarVariantsNode"

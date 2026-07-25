"""Focused owner for ``ivar_filtervariants``."""

from .adapter import IVarFilterVariantsNode as _NodeContract


class IVarFilterVariantsNode(_NodeContract):
    NODE_ID = "ivar_filtervariants"
    UPSTREAM_SYMBOL = "IVarFilterVariantsNode"

"""Focused owner for ``ivar_consensus``."""

from .adapter import IVarConsensusNode as _NodeContract


class IVarConsensusNode(_NodeContract):
    NODE_ID = "ivar_consensus"
    UPSTREAM_SYMBOL = "IVarConsensusNode"

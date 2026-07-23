"""Focused registered owner for ``ucsc_chainnet``."""

from .alignment_adapter import UcscChainNetNode as _NodeContract


class UcscChainNetNode(_NodeContract):
    NODE_ID = "ucsc_chainnet"

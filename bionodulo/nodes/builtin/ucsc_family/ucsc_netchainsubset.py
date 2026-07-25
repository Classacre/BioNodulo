"""Focused registered owner for ``ucsc_netchainsubset``."""

from .chain_net_adapter import UcscNetChainSubsetNode as _NodeContract


class UcscNetChainSubsetNode(_NodeContract):
    NODE_ID = "ucsc_netchainsubset"

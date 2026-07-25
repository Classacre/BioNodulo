"""Focused registered owner for ``ucsc_chainswap``."""

from .chain_net_adapter import UcscChainSwapNode as _NodeContract


class UcscChainSwapNode(_NodeContract):
    NODE_ID = "ucsc_chainswap"

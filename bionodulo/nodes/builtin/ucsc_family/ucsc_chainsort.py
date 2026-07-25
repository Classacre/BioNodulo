"""Focused registered owner for ``ucsc_chainsort``."""

from .chain_net_adapter import UcscChainSortNode as _NodeContract


class UcscChainSortNode(_NodeContract):
    NODE_ID = "ucsc_chainsort"

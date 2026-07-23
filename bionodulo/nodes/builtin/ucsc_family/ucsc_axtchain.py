"""Focused registered owner for ``ucsc_axtchain``."""

from .alignment_adapter import UcscAxtChainNode as _NodeContract


class UcscAxtChainNode(_NodeContract):
    NODE_ID = "ucsc_axtchain"

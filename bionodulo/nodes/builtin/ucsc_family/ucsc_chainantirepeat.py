"""Focused registered owner for ``ucsc_chainantirepeat``."""

from .chain_antirepeat_adapter import UcscChainAntiRepeatNode as _NodeContract


class UcscChainAntiRepeatNode(_NodeContract):
    NODE_ID = "ucsc_chainantirepeat"

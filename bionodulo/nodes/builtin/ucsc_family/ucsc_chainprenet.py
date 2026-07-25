"""Focused registered owner for ``ucsc_chainprenet``."""

from .chain_net_adapter import UcscChainPreNetNode as _NodeContract


class UcscChainPreNetNode(_NodeContract):
    NODE_ID = "ucsc_chainprenet"

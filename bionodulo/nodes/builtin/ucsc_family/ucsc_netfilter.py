"""Focused registered owner for ``ucsc_netfilter``."""

from .chain_net_adapter import UcscNetFilterNode as _NodeContract


class UcscNetFilterNode(_NodeContract):
    NODE_ID = "ucsc_netfilter"

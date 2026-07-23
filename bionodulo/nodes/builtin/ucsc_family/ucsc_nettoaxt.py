"""Focused registered owner for ``ucsc_nettoaxt``."""

from .chain_net_adapter import UcscNetToAxtNode as _NodeContract


class UcscNetToAxtNode(_NodeContract):
    NODE_ID = "ucsc_nettoaxt"

"""Focused registered owner for ``ucsc_netsyntenic``."""

from .chain_net_adapter import UcscNetSyntenicNode as _NodeContract


class UcscNetSyntenicNode(_NodeContract):
    NODE_ID = "ucsc_netsyntenic"

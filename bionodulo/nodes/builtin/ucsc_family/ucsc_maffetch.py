"""Focused registered owner for ``ucsc_maffetch``."""

from .maf_adapter import UcscMafFetchNode as _NodeContract


class UcscMafFetchNode(_NodeContract):
    NODE_ID = "ucsc_maffetch"

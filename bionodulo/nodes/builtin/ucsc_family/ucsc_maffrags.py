"""Focused registered owner for ``ucsc_maffrags``."""

from .maf_adapter import UcscMafFragsNode as _NodeContract


class UcscMafFragsNode(_NodeContract):
    NODE_ID = "ucsc_maffrags"

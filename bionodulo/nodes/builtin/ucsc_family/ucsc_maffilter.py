"""Focused registered owner for ``ucsc_maffilter``."""

from .maf_adapter import UcscMafFilterNode as _NodeContract


class UcscMafFilterNode(_NodeContract):
    NODE_ID = "ucsc_maffilter"

"""Focused registered owner for ``ucsc_mafgene``."""

from .maf_adapter import UcscMafGeneNode as _NodeContract


class UcscMafGeneNode(_NodeContract):
    NODE_ID = "ucsc_mafgene"

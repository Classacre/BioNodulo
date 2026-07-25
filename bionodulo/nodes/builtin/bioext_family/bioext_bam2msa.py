"""Focused owner for ``bioext_bam2msa``."""

from .adapter import BioExtBam2MsaNode as _NodeContract


class BioExtBam2MsaNode(_NodeContract):
    NODE_ID = "bioext_bam2msa"
    UPSTREAM_SYMBOL = "BioExtBam2MsaNode"

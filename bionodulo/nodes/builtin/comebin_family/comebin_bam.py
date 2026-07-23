"""Focused owner for ``comebin_bam``."""

from .adapter import COMEBinBamNode as _NodeContract


class COMEBinBamNode(_NodeContract):
    NODE_ID = "comebin_bam"
    UPSTREAM_SYMBOL = "COMEBinBamNode"

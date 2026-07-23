"""Focused registered owner for ``fatovcf``."""

from .fasta_adapter import FaToVcfNode as _NodeContract


class FaToVcfNode(_NodeContract):
    NODE_ID = "fatovcf"

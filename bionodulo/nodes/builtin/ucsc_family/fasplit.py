"""Focused registered owner for ``fasplit``."""

from .fasta_adapter import FaSplitNode as _NodeContract


class FaSplitNode(_NodeContract):
    NODE_ID = "fasplit"

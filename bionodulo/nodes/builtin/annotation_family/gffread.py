"""Focused registered owner for ``gffread``."""

from .gff_adapter import GffReadNode as _NodeContract


class GffReadNode(_NodeContract):
    NODE_ID = "gffread"

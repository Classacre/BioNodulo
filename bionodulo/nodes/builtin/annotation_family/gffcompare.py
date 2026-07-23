"""Focused registered owner for ``gffcompare``."""

from .gff_adapter import GffCompareNode as _NodeContract


class GffCompareNode(_NodeContract):
    NODE_ID = "gffcompare"

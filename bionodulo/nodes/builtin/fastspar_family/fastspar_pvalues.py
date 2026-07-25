"""Focused owner for ``fastspar_pvalues``."""

from .adapter import FastSparPvaluesNode as _NodeContract


class FastSparPvaluesNode(_NodeContract):
    NODE_ID = "fastspar_pvalues"
    UPSTREAM_SYMBOL = "FastSparPvaluesNode"

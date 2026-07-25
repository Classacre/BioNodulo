"""Focused owner for ``fastspar_reduce``."""

from .adapter import FastSparReduceNode as _NodeContract


class FastSparReduceNode(_NodeContract):
    NODE_ID = "fastspar_reduce"
    UPSTREAM_SYMBOL = "FastSparReduceNode"

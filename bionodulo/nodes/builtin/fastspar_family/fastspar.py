"""Focused owner for ``fastspar``."""

from .adapter import FastSparNode as _NodeContract


class FastSparNode(_NodeContract):
    NODE_ID = "fastspar"
    UPSTREAM_SYMBOL = "FastSparNode"

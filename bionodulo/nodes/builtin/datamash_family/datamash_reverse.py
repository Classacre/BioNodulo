"""Focused registered node for ``datamash_reverse``."""

from .adapter import DatamashReverseNode as _NodeContract


class DatamashReverseNode(_NodeContract):
    NODE_ID = "datamash_reverse"

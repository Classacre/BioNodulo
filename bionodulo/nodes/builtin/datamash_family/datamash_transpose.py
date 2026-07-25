"""Focused registered node for ``datamash_transpose``."""

from .adapter import DatamashTransposeNode as _NodeContract


class DatamashTransposeNode(_NodeContract):
    NODE_ID = "datamash_transpose"

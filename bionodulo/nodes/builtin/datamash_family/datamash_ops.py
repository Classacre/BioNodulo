"""Focused registered node for ``datamash_ops``."""

from .adapter import DatamashOpsNode as _NodeContract


class DatamashOpsNode(_NodeContract):
    NODE_ID = "datamash_ops"

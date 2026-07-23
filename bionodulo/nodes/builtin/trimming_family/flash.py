"""Focused owner for ``flash``."""

from .read_merging_adapter import FLASHNode as _NodeContract


class FLASHNode(_NodeContract):
    NODE_ID = "flash"

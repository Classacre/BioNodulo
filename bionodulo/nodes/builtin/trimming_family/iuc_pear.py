"""Focused owner for ``iuc_pear``."""

from .read_merging_adapter import PEARNode as _NodeContract


class PEARNode(_NodeContract):
    NODE_ID = "iuc_pear"

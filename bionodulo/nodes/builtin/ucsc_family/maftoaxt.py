"""Focused registered owner for ``maftoaxt``."""

from .maf_extra_adapter import MafToAxtNode as _NodeContract


class MafToAxtNode(_NodeContract):
    NODE_ID = "maftoaxt"

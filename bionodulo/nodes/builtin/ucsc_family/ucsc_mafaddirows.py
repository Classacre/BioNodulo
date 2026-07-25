"""Focused registered owner for ``ucsc_mafaddirows``."""

from .maf_adapter import UcscMafAddIRowsNode as _NodeContract


class UcscMafAddIRowsNode(_NodeContract):
    NODE_ID = "ucsc_mafaddirows"

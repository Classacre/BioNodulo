"""Focused owner for ``minia``."""

from .assembly_qc_adapter import MiniaNode as _NodeContract


class MiniaNode(_NodeContract):
    NODE_ID = "minia"

"""Focused owner for ``genomescope``."""

from .assembly_qc_adapter import GenomeScopeNode as _NodeContract


class GenomeScopeNode(_NodeContract):
    NODE_ID = "genomescope"

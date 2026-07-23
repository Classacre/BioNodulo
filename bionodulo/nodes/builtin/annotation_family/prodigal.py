"""Focused owner for ``prodigal``."""

from .microbial_gene_tools_adapter import ProdigalNode as _NodeContract


class ProdigalNode(_NodeContract):
    NODE_ID = "prodigal"

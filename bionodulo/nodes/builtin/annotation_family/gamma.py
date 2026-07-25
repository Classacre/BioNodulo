"""Focused owner for ``gamma``."""

from .microbial_gene_tools_adapter import GAMMANode as _NodeContract


class GAMMANode(_NodeContract):
    NODE_ID = "gamma"

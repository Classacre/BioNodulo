"""Focused owner for ``fraggenescan``."""

from .microbial_gene_tools_adapter import FragGeneScanNode as _NodeContract


class FragGeneScanNode(_NodeContract):
    NODE_ID = "fraggenescan"

"""Focused owner for ``gamma_s``."""

from .microbial_gene_tools_adapter import GAMMASNode as _NodeContract


class GAMMASNode(_NodeContract):
    NODE_ID = "gamma_s"

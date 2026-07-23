"""Focused owner for ``abritamr``."""

from .microbial_gene_tools_adapter import AbriTAMRNode as _NodeContract


class AbriTAMRNode(_NodeContract):
    NODE_ID = "abritamr"

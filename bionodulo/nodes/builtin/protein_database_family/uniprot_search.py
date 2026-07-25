"""Focused registered node for ``uniprot_search``."""

from bionodulo.nodes.builtin.protein_database_family.uniprot_adapter import UniProtSearchNode as _NodeContract


class UniProtSearchNode(_NodeContract):
    NODE_ID = 'uniprot_search'

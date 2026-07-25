"""Focused registered node for ``uniprot_retrieve``."""

from bionodulo.nodes.builtin.protein_database_family.uniprot_adapter import UniProtRetrieveNode as _NodeContract


class UniProtRetrieveNode(_NodeContract):
    NODE_ID = 'uniprot_retrieve'

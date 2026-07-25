"""Compatibility facade for focused UniProt REST API nodes."""

from bionodulo.nodes.builtin.protein_database_family.uniprot import (
    UniProtRetrieveNode,
    UniProtSearchNode,
)

__all__ = ["UniProtRetrieveNode", "UniProtSearchNode"]

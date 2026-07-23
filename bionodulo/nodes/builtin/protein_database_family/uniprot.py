"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.protein_database_family.uniprot_adapter as _adapter
from bionodulo.nodes.builtin.protein_database_family.uniprot_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.protein_database_family.uniprot_retrieve import UniProtRetrieveNode
from bionodulo.nodes.builtin.protein_database_family.uniprot_search import UniProtSearchNode

__all__ = ['UniProtRetrieveNode', 'UniProtSearchNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

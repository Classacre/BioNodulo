"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.protein_database_family.rcsb_pdb_adapter as _adapter
from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.protein_database_family.pdb_download import PDBDownloadNode
from bionodulo.nodes.builtin.protein_database_family.pdb_retrieve import PDBRetrieveNode

__all__ = ['PDBDownloadNode', 'PDBRetrieveNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

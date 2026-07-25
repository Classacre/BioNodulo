"""Focused registered node for ``alphafold_db``."""

import bionodulo.nodes.builtin.protein_database_family.alphafold_db_adapter as _adapter
from bionodulo.nodes.builtin.protein_database_family.alphafold_db_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.protein_database_family.alphafold_db_adapter import AlphaFoldDBNode as _NodeContract
globals().pop('AlphaFoldNode', None)


class AlphaFoldDBNode(_NodeContract):
    NODE_ID = 'alphafold_db'

__all__ = ['AlphaFoldDBNode', 'AlphaFoldNode']  # noqa: F405


def __getattr__(name: str):
    if name == 'AlphaFoldNode':
        from bionodulo.nodes.builtin.protein_database_family.alphafold import AlphaFoldNode

        return AlphaFoldNode
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_adapter)))

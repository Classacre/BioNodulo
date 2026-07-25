"""Focused registered node for ``alphafold``."""

from bionodulo.nodes.builtin.protein_database_family.alphafold_db_adapter import AlphaFoldNode as _NodeContract
from bionodulo.nodes.builtin.protein_database_family.alphafold_db import AlphaFoldDBNode


class AlphaFoldNode(_NodeContract, AlphaFoldDBNode):
    NODE_ID = 'alphafold'

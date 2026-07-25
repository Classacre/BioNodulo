"""Focused registered node for ``pdb_retrieve``."""

from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb_adapter import PDBRetrieveNode as _NodeContract
from bionodulo.nodes.builtin.protein_database_family.pdb_download import PDBDownloadNode


class PDBRetrieveNode(_NodeContract, PDBDownloadNode):
    NODE_ID = 'pdb_retrieve'

"""Focused registered node for ``pdb_download``."""

from bionodulo.nodes.builtin.protein_database_family.rcsb_pdb_adapter import PDBDownloadNode as _NodeContract


class PDBDownloadNode(_NodeContract):
    NODE_ID = 'pdb_download'

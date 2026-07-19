"""Stable owner for ``pangenome_gene``."""

from .legacy import _PangenomeGeneContract


class PangenomeGeneNode(_PangenomeGeneContract):
    NODE_ID = "pangenome_gene"

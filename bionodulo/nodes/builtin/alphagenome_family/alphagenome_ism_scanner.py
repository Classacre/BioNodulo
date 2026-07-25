"""Focused owner for ``alphagenome_ism_scanner``."""

from .adapter import AlphaGenomeISMScannerNode as _NodeContract


class AlphaGenomeISMScannerNode(_NodeContract):
    NODE_ID = "alphagenome_ism_scanner"

"""Stable owner for ``beacon2_gene``."""

from .adapter import _Beacon2GeneContract


class Beacon2GeneNode(_Beacon2GeneContract):
    NODE_ID = "beacon2_gene"
    UPSTREAM_SYMBOL = "Beacon2GeneNode"

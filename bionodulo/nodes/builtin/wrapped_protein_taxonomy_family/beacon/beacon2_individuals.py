"""Stable owner for ``beacon2_individuals``."""

from .adapter import _Beacon2IndividualsContract


class Beacon2IndividualsNode(_Beacon2IndividualsContract):
    NODE_ID = "beacon2_individuals"
    UPSTREAM_SYMBOL = "Beacon2IndividualsNode"

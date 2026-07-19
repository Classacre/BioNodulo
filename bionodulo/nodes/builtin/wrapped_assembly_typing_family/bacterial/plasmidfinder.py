"""Stable owner for ``plasmidfinder``."""

from .typing_adapter import _PlasmidFinderContract


class PlasmidFinderNode(_PlasmidFinderContract):
    NODE_ID = "plasmidfinder"
    UPSTREAM_SYMBOL = "PlasmidFinderNode"

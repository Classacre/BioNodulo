"""Focused owner for ``plasmidfinder``."""

from bionodulo.nodes.builtin._bacterial_typing_adapter import _PlasmidFinderContract


class PlasmidFinderNode(_PlasmidFinderContract):
    NODE_ID = "plasmidfinder"
    UPSTREAM_SYMBOL = "PlasmidFinderNode"

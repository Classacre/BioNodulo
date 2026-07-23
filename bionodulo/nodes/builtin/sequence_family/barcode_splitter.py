"""Focused owner for ``barcode_splitter``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _BarcodeSplitterContract


class BarcodeSplitterNode(_BarcodeSplitterContract):
    NODE_ID = "barcode_splitter"
    UPSTREAM_SYMBOL = "BarcodeSplitterNode"

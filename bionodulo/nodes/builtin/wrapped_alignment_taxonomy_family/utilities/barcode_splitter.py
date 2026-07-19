"""Stable owner for ``barcode_splitter``."""

from .adapter import _BarcodeSplitterContract


class BarcodeSplitterNode(_BarcodeSplitterContract):
    NODE_ID = "barcode_splitter"
    UPSTREAM_SYMBOL = "BarcodeSplitterNode"

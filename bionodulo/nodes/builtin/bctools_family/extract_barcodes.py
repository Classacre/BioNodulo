"""Focused owner for ``bctools_extract_barcodes``."""

from .adapter import _BctoolsExtractBarcodesContract


class BctoolsExtractBarcodesNode(_BctoolsExtractBarcodesContract):
    NODE_ID = "bctools_extract_barcodes"
    UPSTREAM_SYMBOL = "BctoolsExtractBarcodesNode"

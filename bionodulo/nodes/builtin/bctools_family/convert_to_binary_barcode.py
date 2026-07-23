"""Focused owner for ``bctools_convert_to_binary_barcode``."""

from .adapter import _BctoolsConvertToBinaryBarcodeContract


class BctoolsConvertToBinaryBarcodeNode(_BctoolsConvertToBinaryBarcodeContract):
    NODE_ID = "bctools_convert_to_binary_barcode"
    UPSTREAM_SYMBOL = "BctoolsConvertToBinaryBarcodeNode"

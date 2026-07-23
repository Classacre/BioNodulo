"""Focused registered owner for ``beacon2_csv2xlsx``."""

from .wrapper_adapter import Beacon2Csv2XlsxNode as _NodeContract


class Beacon2Csv2XlsxNode(_NodeContract):
    NODE_ID = "beacon2_csv2xlsx"

"""Focused registered owner for ``beacon2_import``."""

from .wrapper_adapter import Beacon2ImportNode as _NodeContract


class Beacon2ImportNode(_NodeContract):
    NODE_ID = "beacon2_import"

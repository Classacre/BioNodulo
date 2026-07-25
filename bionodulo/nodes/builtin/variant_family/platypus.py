"""Stable owner for ``platypus``."""

from .legacy import _PlatypusContract


class PlatypusNode(_PlatypusContract):
    NODE_ID = "platypus"

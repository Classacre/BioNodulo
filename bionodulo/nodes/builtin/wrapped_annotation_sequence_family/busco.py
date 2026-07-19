"""Stable owner for ``busco``."""

from .legacy import _BUSCOContract


class BUSCONode(_BUSCOContract):
    NODE_ID = "busco"

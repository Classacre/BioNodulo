"""Stable owner for ``taxpasta``."""

from .adapter import _TaxpastaContract


class TaxpastaNode(_TaxpastaContract):
    NODE_ID = "taxpasta"
    UPSTREAM_SYMBOL = "TaxpastaNode"

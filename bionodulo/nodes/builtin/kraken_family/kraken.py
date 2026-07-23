"""Stable owner for ``kraken``."""

from .adapter import _KrakenContract


class KrakenNode(_KrakenContract):
    NODE_ID = "kraken"
    UPSTREAM_SYMBOL = "KrakenNode"

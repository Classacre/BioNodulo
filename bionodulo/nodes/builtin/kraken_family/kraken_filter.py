"""Stable owner for ``kraken_filter``."""

from .adapter import _KrakenFilterContract


class KrakenFilterNode(_KrakenFilterContract):
    NODE_ID = "kraken_filter"
    UPSTREAM_SYMBOL = "KrakenFilterNode"

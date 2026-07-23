"""Stable owner for ``kraken_translate``."""

from .adapter import _KrakenTranslateContract


class KrakenTranslateNode(_KrakenTranslateContract):
    NODE_ID = "kraken_translate"
    UPSTREAM_SYMBOL = "KrakenTranslateNode"

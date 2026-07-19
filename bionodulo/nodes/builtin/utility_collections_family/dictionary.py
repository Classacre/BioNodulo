"""Stable owner for the ``dictionary`` node."""

from .adapter import _DictionaryContract


class DictionaryNode(_DictionaryContract):
    NODE_ID = "dictionary"
    UPSTREAM_SYMBOL = "DictionaryNode"

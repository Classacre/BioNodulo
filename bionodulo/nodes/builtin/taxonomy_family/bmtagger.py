"""Stable owner for ``bmtagger``."""

from .adapter import _BMTaggerContract


class BMTaggerNode(_BMTaggerContract):
    NODE_ID = "bmtagger"
    UPSTREAM_SYMBOL = "BMTaggerNode"

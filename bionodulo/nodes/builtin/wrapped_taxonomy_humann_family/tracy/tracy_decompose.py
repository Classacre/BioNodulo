"""Stable owner for ``tracy_decompose``."""

from .adapter import _TracyDecomposeContract


class TracyDecomposeNode(_TracyDecomposeContract):
    NODE_ID = "tracy_decompose"
    UPSTREAM_SYMBOL = "TracyDecomposeNode"

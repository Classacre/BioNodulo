"""Stable owner for ``tracy_assemble``."""

from .adapter import _TracyAssembleContract


class TracyAssembleNode(_TracyAssembleContract):
    NODE_ID = "tracy_assemble"
    UPSTREAM_SYMBOL = "TracyAssembleNode"

"""Stable owner for ``tracy_align``."""

from .adapter import _TracyAlignContract


class TracyAlignNode(_TracyAlignContract):
    NODE_ID = "tracy_align"
    UPSTREAM_SYMBOL = "TracyAlignNode"

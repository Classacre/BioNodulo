"""Stable owner for ``tracy_basecall``."""

from .adapter import _TracyBasecallContract


class TracyBasecallNode(_TracyBasecallContract):
    NODE_ID = "tracy_basecall"
    UPSTREAM_SYMBOL = "TracyBasecallNode"

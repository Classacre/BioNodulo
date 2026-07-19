"""Workflow cache-control node."""

from .adapter import CacheControlNode as _CacheControlContract


class CacheControlNode(_CacheControlContract):
    """Read, write, inspect, or invalidate workflow cache entries."""

    NODE_ID = "cache_control"

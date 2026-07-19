"""Workflow memoization node."""

from .adapter import MemoizeNode as _MemoizeContract


class MemoizeNode(_MemoizeContract):
    """Memoize a value under a deterministic content key."""

    NODE_ID = "memoize"

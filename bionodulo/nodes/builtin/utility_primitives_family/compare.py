"""Numeric comparison utility node."""

from .adapter import CompareNode as _CompareContract


class CompareNode(_CompareContract):
    """Compare two finite numeric values."""

    NODE_ID = "compare"

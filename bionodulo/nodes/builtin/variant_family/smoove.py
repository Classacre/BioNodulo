"""Stable owner for ``smoove``."""

from .legacy import _SmooveContract


class SmooveNode(_SmooveContract):
    NODE_ID = "smoove"

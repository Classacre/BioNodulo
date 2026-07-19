"""Stable owner for ``circos``."""

from ..adapter import _CircosContract


class CircosNode(_CircosContract):
    NODE_ID = "circos"

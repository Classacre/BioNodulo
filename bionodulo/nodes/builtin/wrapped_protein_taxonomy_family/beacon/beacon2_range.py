"""Stable owner for ``beacon2_range``."""

from .adapter import _Beacon2RangeContract


class Beacon2RangeNode(_Beacon2RangeContract):
    NODE_ID = "beacon2_range"
    UPSTREAM_SYMBOL = "Beacon2RangeNode"

"""Stable owner for ``beacon2_runs``."""

from .adapter import _Beacon2RunsContract


class Beacon2RunsNode(_Beacon2RunsContract):
    NODE_ID = "beacon2_runs"
    UPSTREAM_SYMBOL = "Beacon2RunsNode"

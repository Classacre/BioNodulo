"""Stable owner for ``beacon2_analyses``."""

from .adapter import _Beacon2AnalysesContract


class Beacon2AnalysesNode(_Beacon2AnalysesContract):
    NODE_ID = "beacon2_analyses"
    UPSTREAM_SYMBOL = "Beacon2AnalysesNode"

"""Focused owner for ``drep_compare``."""

from .adapter import DrepCompareNode as _NodeContract


class DrepCompareNode(_NodeContract):
    NODE_ID = "drep_compare"
    UPSTREAM_SYMBOL = "DrepCompareNode"

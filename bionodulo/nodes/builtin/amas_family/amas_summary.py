"""Focused owner for ``amas_summary``."""

from .adapter import AMASSummaryNode as _NodeContract


class AMASSummaryNode(_NodeContract):
    NODE_ID = "amas_summary"

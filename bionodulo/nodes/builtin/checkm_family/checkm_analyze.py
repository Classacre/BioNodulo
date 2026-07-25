"""Focused owner for ``checkm_analyze``."""

from .adapter import _CheckMAnalyzeContract


class CheckMAnalyzeNode(_CheckMAnalyzeContract):
    NODE_ID = "checkm_analyze"
    UPSTREAM_SYMBOL = "CheckMAnalyzeNode"

"""Stable owner for ``abricate_summary``."""

from .adapter import _ABRicateSummaryContract


class ABRicateSummaryNode(_ABRicateSummaryContract):
    NODE_ID = "abricate_summary"
    UPSTREAM_SYMBOL = "ABRicateSummaryNode"

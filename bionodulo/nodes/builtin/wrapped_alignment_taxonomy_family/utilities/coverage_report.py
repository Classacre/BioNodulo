"""Stable owner for ``CoverageReport2``."""

from .adapter import _CoverageReportContract


class CoverageReportNode(_CoverageReportContract):
    NODE_ID = "CoverageReport2"
    UPSTREAM_SYMBOL = "CoverageReportNode"

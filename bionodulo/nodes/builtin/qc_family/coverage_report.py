"""Focused owner for ``CoverageReport2``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _CoverageReportContract


class CoverageReportNode(_CoverageReportContract):
    NODE_ID = "CoverageReport2"
    UPSTREAM_SYMBOL = "CoverageReportNode"

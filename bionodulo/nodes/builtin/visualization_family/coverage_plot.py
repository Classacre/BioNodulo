"""Stable owner for the ``coverage_plot`` node."""

from .adapter import _CoveragePlotContract


class CoveragePlotNode(_CoveragePlotContract):
    """Render BAM, CRAM, BigWig, bedGraph, or tabular genomic coverage."""

    NODE_ID = "coverage_plot"
    UPSTREAM_SYMBOL = "CoveragePlotNode"

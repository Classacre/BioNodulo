"""Stable owner for the ``ma_plot`` node."""

from .adapter import _MAPlotContract


class MAPlotNode(_MAPlotContract):
    """Render differential-expression mean abundance against fold change."""

    NODE_ID = "ma_plot"
    UPSTREAM_SYMBOL = "MAPlotNode"

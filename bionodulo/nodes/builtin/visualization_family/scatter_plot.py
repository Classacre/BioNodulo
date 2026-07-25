"""Stable owner for the ``scatter_plot`` node."""

from .adapter import _ScatterPlotContract


class ScatterPlotNode(_ScatterPlotContract):
    """Render numeric X/Y observations with optional grouping and regression."""

    NODE_ID = "scatter_plot"
    UPSTREAM_SYMBOL = "ScatterPlotNode"

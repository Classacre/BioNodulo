"""Stable owner for the ``forest_plot`` node."""

from .adapter import _ForestPlotContract


class ForestPlotNode(_ForestPlotContract):
    """Render study effects and confidence intervals from a table."""

    NODE_ID = "forest_plot"
    UPSTREAM_SYMBOL = "ForestPlotNode"

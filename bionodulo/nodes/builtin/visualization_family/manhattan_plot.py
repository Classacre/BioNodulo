"""Stable owner for the ``manhattan_plot`` node."""

from .adapter import _ManhattanPlotContract


class ManhattanPlotNode(_ManhattanPlotContract):
    """Render chromosome-ordered association p-values and thresholds."""

    NODE_ID = "manhattan_plot"
    UPSTREAM_SYMBOL = "ManhattanPlotNode"

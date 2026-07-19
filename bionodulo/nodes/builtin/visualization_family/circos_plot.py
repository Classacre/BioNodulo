"""Stable owner for the ``circos_plot`` node."""

from .adapter import _CircosPlotContract


class CircosPlotNode(_CircosPlotContract):
    """Render chromosome sectors and optional tracks without invoking Circos."""

    NODE_ID = "circos_plot"
    UPSTREAM_SYMBOL = "CircosPlotNode"

"""Stable owner for the ``volcano_plot`` node."""

from .adapter import _VolcanoPlotContract


class VolcanoPlotNode(_VolcanoPlotContract):
    """Render differential-expression significance against fold change."""

    NODE_ID = "volcano_plot"
    UPSTREAM_SYMBOL = "VolcanoPlotNode"

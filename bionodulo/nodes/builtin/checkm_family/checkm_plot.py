"""Focused owner for ``checkm_plot``."""

from .adapter import _CheckMPlotContract


class CheckMPlotNode(_CheckMPlotContract):
    NODE_ID = "checkm_plot"
    UPSTREAM_SYMBOL = "CheckMPlotNode"

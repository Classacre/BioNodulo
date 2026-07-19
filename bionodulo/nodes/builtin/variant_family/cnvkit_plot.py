"""Stable owner for ``cnvkit_plot``."""

from .legacy import _CNVkitPlotContract


class CNVkitPlotNode(_CNVkitPlotContract):
    NODE_ID = "cnvkit_plot"

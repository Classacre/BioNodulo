"""Stable owner for the ``line_chart`` node."""

from .adapter import _LineChartContract


class LineChartNode(_LineChartContract):
    """Render one or more numeric series over a shared X column."""

    NODE_ID = "line_chart"
    UPSTREAM_SYMBOL = "LineChartNode"

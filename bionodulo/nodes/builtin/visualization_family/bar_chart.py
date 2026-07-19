"""Stable owner for the ``bar_chart`` node."""

from .adapter import _BarChartContract


class BarChartNode(_BarChartContract):
    """Render categorical values as a native static or Plotly HTML chart."""

    NODE_ID = "bar_chart"
    UPSTREAM_SYMBOL = "BarChartNode"

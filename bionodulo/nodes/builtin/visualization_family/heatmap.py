"""Stable owner for the ``heatmap`` node."""

from .adapter import _HeatmapContract


class HeatmapNode(_HeatmapContract):
    """Render a labeled numeric matrix with optional scaling and clustering."""

    NODE_ID = "heatmap"
    UPSTREAM_SYMBOL = "HeatmapNode"

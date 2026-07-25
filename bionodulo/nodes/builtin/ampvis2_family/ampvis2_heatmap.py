"""Focused registered node for ``ampvis2_heatmap``."""

from .abundance_adapter import Ampvis2HeatmapNode as _NodeContract


class Ampvis2HeatmapNode(_NodeContract):
    NODE_ID = "ampvis2_heatmap"

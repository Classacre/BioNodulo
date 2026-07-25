"""Focused registered owner for ``heinz_visualization``."""

from .adapter import HeinzVisualizationNode as _NodeContract


class HeinzVisualizationNode(_NodeContract):
    NODE_ID = "heinz_visualization"

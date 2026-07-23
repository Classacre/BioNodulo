"""Stable owner for ``circos_interval_to_tile``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CircosIntervalToTileContract


class CircosIntervalToTileNode(_CircosIntervalToTileContract):
    NODE_ID = "circos_interval_to_tile"

"""Stable owner for ``circos``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CircosContract


class CircosNode(_CircosContract):
    NODE_ID = "circos"

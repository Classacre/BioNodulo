"""Stable owner for ``circos_tableviewer``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CircosTableviewerContract


class CircosTableviewerNode(_CircosTableviewerContract):
    NODE_ID = "circos_tableviewer"

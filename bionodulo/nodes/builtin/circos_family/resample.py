"""Stable owner for ``circos_resample``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CircosResampleContract


class CircosResampleNode(_CircosResampleContract):
    NODE_ID = "circos_resample"

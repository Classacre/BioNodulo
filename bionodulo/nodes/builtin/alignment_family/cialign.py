"""Stable owner for ``cialign``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CIAlignContract


class CIAlignNode(_CIAlignContract):
    NODE_ID = "cialign"

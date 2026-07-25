"""Stable owner for ``chopper``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _ChopperContract


class ChopperNode(_ChopperContract):
    NODE_ID = "chopper"

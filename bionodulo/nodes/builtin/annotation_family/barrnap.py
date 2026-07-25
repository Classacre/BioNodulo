"""Stable owner for ``barrnap``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _BarrnapContract


class BarrnapNode(_BarrnapContract):
    NODE_ID = "barrnap"

"""Stable owner for ``filtlong``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _FiltlongContract


class FiltlongNode(_FiltlongContract):
    NODE_ID = "filtlong"

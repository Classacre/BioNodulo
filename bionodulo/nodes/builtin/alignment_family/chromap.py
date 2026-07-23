"""Stable owner for ``chromap``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _ChromapContract


class ChromapNode(_ChromapContract):
    NODE_ID = "chromap"

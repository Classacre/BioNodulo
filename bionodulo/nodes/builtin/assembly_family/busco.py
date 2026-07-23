"""Focused owner for ``busco``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _BUSCOContract


class BUSCONode(_BUSCOContract):
    NODE_ID = "busco"

"""Focused owner for ``artic_minion``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _ArticMinionContract


class ArticMinionNode(_ArticMinionContract):
    NODE_ID = "artic_minion"

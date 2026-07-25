"""Focused owner for ``augustus_training``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _AugustusTrainingContract


class AugustusTrainingNode(_AugustusTrainingContract):
    NODE_ID = "augustus_training"

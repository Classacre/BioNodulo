"""Stable owner for ``augustus_training``."""

from .legacy import _AugustusTrainingContract


class AugustusTrainingNode(_AugustusTrainingContract):
    NODE_ID = "augustus_training"

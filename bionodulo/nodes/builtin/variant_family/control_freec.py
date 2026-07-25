"""Stable owner for ``control_freec``."""

from .legacy import _ControlFREECContract


class ControlFREECNode(_ControlFREECContract):
    NODE_ID = "control_freec"

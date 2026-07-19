"""Stable owner for ``vg_call``."""

from .legacy import _VGCallContract


class VGCallNode(_VGCallContract):
    NODE_ID = "vg_call"

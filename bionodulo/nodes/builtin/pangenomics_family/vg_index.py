"""Stable owner for ``vg_index``."""

from .legacy import _VGIndexContract


class VGIndexNode(_VGIndexContract):
    NODE_ID = "vg_index"

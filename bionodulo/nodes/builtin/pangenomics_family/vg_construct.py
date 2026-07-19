"""Stable owner for ``vg_construct``."""

from .legacy import _VGConstructContract


class VGConstructNode(_VGConstructContract):
    NODE_ID = "vg_construct"

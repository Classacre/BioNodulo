"""Stable owner for ``vg_map``."""

from .legacy import _VGMapContract


class VGMapNode(_VGMapContract):
    NODE_ID = "vg_map"

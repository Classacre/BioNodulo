"""Stable owner for ``pbsv``."""

from .legacy import _PBSVContract


class PBSVNode(_PBSVContract):
    NODE_ID = "pbsv"

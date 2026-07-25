"""Stable owner for ``cutesv``."""

from .legacy import _CuteSVContract


class CuteSVNode(_CuteSVContract):
    NODE_ID = "cutesv"

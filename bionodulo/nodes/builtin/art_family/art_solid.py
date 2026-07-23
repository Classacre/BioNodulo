"""Focused owner for ``art_solid``."""

from .adapter import ARTSOLiDNode as _NodeContract


class ARTSOLiDNode(_NodeContract):
    NODE_ID = "art_solid"

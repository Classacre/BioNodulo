"""Focused owner for ``art_illumina``."""

from .adapter import ARTIlluminaNode as _NodeContract


class ARTIlluminaNode(_NodeContract):
    NODE_ID = "art_illumina"

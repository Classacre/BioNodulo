"""Focused registered owner for ``ucsc_wigtobigwig``."""

from .sequence_tracks_adapter import UcscWigToBigWigNode as _NodeContract


class UcscWigToBigWigNode(_NodeContract):
    NODE_ID = "ucsc_wigtobigwig"

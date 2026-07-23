"""Focused registered owner for ``ucsc-twobittofa``."""

from .sequence_tracks_adapter import UcscTwoBitToFaNode as _NodeContract


class UcscTwoBitToFaNode(_NodeContract):
    NODE_ID = "ucsc-twobittofa"

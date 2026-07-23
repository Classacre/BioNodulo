"""Focused registered owner for ``ucsc_axtomaf``."""

from .sequence_tracks_adapter import UcscAxtToMafNode as _NodeContract


class UcscAxtToMafNode(_NodeContract):
    NODE_ID = "ucsc_axtomaf"

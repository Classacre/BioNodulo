"""Stable owner for ``beacon2_sequence``."""

from .adapter import _Beacon2SequenceContract


class Beacon2SequenceNode(_Beacon2SequenceContract):
    NODE_ID = "beacon2_sequence"
    UPSTREAM_SYMBOL = "Beacon2SequenceNode"

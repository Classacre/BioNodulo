"""Focused registered node for ``seqsero2``."""

from .adapter import SeqSero2Node as _NodeContract


class SeqSero2Node(_NodeContract):
    NODE_ID = "seqsero2"

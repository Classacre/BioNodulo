"""Stable owner for ``cite_seq_count``."""

from ..adapter import _CiteSeqCountContract


class CiteSeqCountNode(_CiteSeqCountContract):
    NODE_ID = "cite_seq_count"

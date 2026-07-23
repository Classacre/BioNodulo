"""Stable owner for ``cite_seq_count``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CiteSeqCountContract


class CiteSeqCountNode(_CiteSeqCountContract):
    NODE_ID = "cite_seq_count"

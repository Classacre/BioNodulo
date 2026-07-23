"""Focused registered node for ``deseq2_analysis``."""

from bionodulo.nodes.builtin.r_family.deseq2_adapter import DESeq2Node as _NodeContract


class DESeq2Node(_NodeContract):
    NODE_ID = 'deseq2_analysis'

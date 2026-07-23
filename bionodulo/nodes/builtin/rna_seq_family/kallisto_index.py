"""Focused registered node for ``kallisto_index``."""

from bionodulo.nodes.builtin.rna_seq_family.kallisto_adapter import KallistoIndexNode as _NodeContract


class KallistoIndexNode(_NodeContract):
    NODE_ID = 'kallisto_index'

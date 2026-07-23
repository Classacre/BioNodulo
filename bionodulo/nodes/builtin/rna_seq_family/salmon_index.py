"""Focused registered node for ``salmon_index``."""

from bionodulo.nodes.builtin.rna_seq_family.salmon_adapter import SalmonIndexNode as _NodeContract


class SalmonIndexNode(_NodeContract):
    NODE_ID = 'salmon_index'

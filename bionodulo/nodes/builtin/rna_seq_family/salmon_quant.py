"""Focused registered node for ``salmon_quant``."""

from bionodulo.nodes.builtin.rna_seq_family.salmon_adapter import SalmonQuantNode as _NodeContract


class SalmonQuantNode(_NodeContract):
    NODE_ID = 'salmon_quant'

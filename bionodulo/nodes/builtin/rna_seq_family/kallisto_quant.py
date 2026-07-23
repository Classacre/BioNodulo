"""Focused registered node for ``kallisto_quant``."""

from bionodulo.nodes.builtin.rna_seq_family.kallisto_adapter import KallistoQuantNode as _NodeContract


class KallistoQuantNode(_NodeContract):
    NODE_ID = 'kallisto_quant'

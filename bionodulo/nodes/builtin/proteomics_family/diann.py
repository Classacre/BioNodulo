"""Focused registered node for ``diann``."""

from bionodulo.nodes.builtin.proteomics_family.dia_nn_adapter import DIANNAliasNode as _NodeContract
from bionodulo.nodes.builtin.proteomics_family.dia_nn import DIANNNode


class DIANNAliasNode(_NodeContract, DIANNNode):
    NODE_ID = 'diann'

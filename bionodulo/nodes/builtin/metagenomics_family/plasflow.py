"""Focused owner for ``plasflow``."""

from bionodulo.nodes.builtin.assembly_family.assembly_qc_adapter import (
    PlasFlowNode as _NodeContract,
)


class PlasFlowNode(_NodeContract):
    NODE_ID = "plasflow"

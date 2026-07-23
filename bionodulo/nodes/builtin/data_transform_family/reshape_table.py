"""Focused registered node for ``reshape_table``."""

from bionodulo.nodes.builtin.data_transform_family.pivot_table_adapter import ReshapeTableNode as _NodeContract
from bionodulo.nodes.builtin.data_transform_family.pivot_table import PivotTableNode


class ReshapeTableNode(_NodeContract, PivotTableNode):
    NODE_ID = 'reshape_table'

"""Focused registered node for ``addName``."""

from .add_input_name_as_column import AddInputNameAsColumnNode
from .columns_adapter import AddInputNameAsColumnGalaxyNode as _NodeContract


class AddInputNameAsColumnGalaxyNode(_NodeContract, AddInputNameAsColumnNode):
    NODE_ID = "addName"

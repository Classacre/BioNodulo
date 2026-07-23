"""Focused registered node for ``add_input_name_as_column``."""

from .columns_adapter import AddInputNameAsColumnNode as _NodeContract


class AddInputNameAsColumnNode(_NodeContract):
    NODE_ID = "add_input_name_as_column"

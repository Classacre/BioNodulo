"""Focused registered node for ``column_remove_by_header``."""

from .columns_adapter import ColumnRemoveByHeaderNode as _NodeContract


class ColumnRemoveByHeaderNode(_NodeContract):
    NODE_ID = "column_remove_by_header"

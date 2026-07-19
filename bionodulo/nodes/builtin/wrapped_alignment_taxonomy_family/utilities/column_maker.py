"""Stable owner for ``Add_a_column1``."""

from .adapter import _ColumnMakerContract


class ColumnMakerNode(_ColumnMakerContract):
    NODE_ID = "Add_a_column1"
    UPSTREAM_SYMBOL = "ColumnMakerNode"

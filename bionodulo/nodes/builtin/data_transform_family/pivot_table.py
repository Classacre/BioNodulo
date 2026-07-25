"""Focused registered node for ``pivot_table``."""

import bionodulo.nodes.builtin.data_transform_family.pivot_table_adapter as _adapter
from bionodulo.nodes.builtin.data_transform_family.pivot_table_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.data_transform_family.pivot_table_adapter import PivotTableNode as _NodeContract
globals().pop('ReshapeTableNode', None)


class PivotTableNode(_NodeContract):
    NODE_ID = 'pivot_table'

__all__ = ['PivotTableNode', 'ReshapeTableNode']  # noqa: F405


def __getattr__(name: str):
    if name == 'ReshapeTableNode':
        from bionodulo.nodes.builtin.data_transform_family.reshape_table import ReshapeTableNode

        return ReshapeTableNode
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_adapter)))

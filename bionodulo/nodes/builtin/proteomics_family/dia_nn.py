"""Focused registered node for ``dia_nn``."""

import bionodulo.nodes.builtin.proteomics_family.dia_nn_adapter as _adapter
from bionodulo.nodes.builtin.proteomics_family.dia_nn_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.proteomics_family.dia_nn_adapter import DIANNNode as _NodeContract
globals().pop('DIANNAliasNode', None)


class DIANNNode(_NodeContract):
    NODE_ID = 'dia_nn'

__all__ = ['DIANNNode', 'DIANNAliasNode']  # noqa: F405


def __getattr__(name: str):
    if name == 'DIANNAliasNode':
        from bionodulo.nodes.builtin.proteomics_family.diann import DIANNAliasNode

        return DIANNAliasNode
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_adapter)))

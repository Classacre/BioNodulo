"""Focused registered node for ``qualimap``."""

import bionodulo.nodes.builtin.qc_family.qualimap_adapter as _adapter
from bionodulo.nodes.builtin.qc_family.qualimap_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.qc_family.qualimap_adapter import QualiMapAliasNode as _NodeContract
from bionodulo.nodes.builtin.qc_family.qualimap_bamqc import QualiMapNode


class QualiMapAliasNode(_NodeContract, QualiMapNode):
    NODE_ID = 'qualimap'

__all__ = ['QualiMapAliasNode', 'QualiMapNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

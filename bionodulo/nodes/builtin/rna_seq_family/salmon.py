"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.rna_seq_family.salmon_adapter as _adapter
from bionodulo.nodes.builtin.rna_seq_family.salmon_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.rna_seq_family.salmon_index import SalmonIndexNode
from bionodulo.nodes.builtin.rna_seq_family.salmon_quant import SalmonQuantNode

__all__ = ['SalmonIndexNode', 'SalmonQuantNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.rna_seq_family.kallisto_adapter as _adapter
from bionodulo.nodes.builtin.rna_seq_family.kallisto_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.rna_seq_family.kallisto_index import KallistoIndexNode
from bionodulo.nodes.builtin.rna_seq_family.kallisto_quant import KallistoQuantNode

__all__ = ['KallistoIndexNode', 'KallistoQuantNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

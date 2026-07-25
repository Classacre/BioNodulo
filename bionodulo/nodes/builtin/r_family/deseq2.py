"""Focused registered node for ``deseq2``."""

import bionodulo.nodes.builtin.r_family.deseq2_adapter as _adapter
from bionodulo.nodes.builtin.r_family.deseq2_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.r_family.deseq2_adapter import DESeq2AliasNode as _NodeContract
from bionodulo.nodes.builtin.r_family.deseq2_analysis import DESeq2Node


class DESeq2AliasNode(_NodeContract, DESeq2Node):
    NODE_ID = 'deseq2'

__all__ = ['DESeq2AliasNode', 'DESeq2Node']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

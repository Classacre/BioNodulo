"""Focused registered node for ``medaka_consensus``."""

import bionodulo.nodes.builtin.long_read_family.medaka_consensus_adapter as _adapter
from bionodulo.nodes.builtin.long_read_family.medaka_consensus_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.long_read_family.medaka_consensus_adapter import MedakaConsensusNode as _NodeContract
globals().pop('MedakaNode', None)


class MedakaConsensusNode(_NodeContract):
    NODE_ID = 'medaka_consensus'

__all__ = ['MedakaConsensusNode', 'MedakaNode']  # noqa: F405


def __getattr__(name: str):
    if name == 'MedakaNode':
        from bionodulo.nodes.builtin.long_read_family.medaka import MedakaNode

        return MedakaNode
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(dir(_adapter)))

"""Focused registered node for ``medaka``."""

from bionodulo.nodes.builtin.long_read_family.medaka_consensus_adapter import MedakaNode as _NodeContract
from bionodulo.nodes.builtin.long_read_family.medaka_consensus import MedakaConsensusNode


class MedakaNode(_NodeContract, MedakaConsensusNode):
    NODE_ID = 'medaka'

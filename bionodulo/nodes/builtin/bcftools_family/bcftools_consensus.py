"""Focused registered node for ``bcftools_consensus``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsConsensusNode as _NodeContract


class BCFtoolsConsensusNode(_NodeContract):
    NODE_ID = 'bcftools_consensus'

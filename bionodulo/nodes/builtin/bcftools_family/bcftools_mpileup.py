"""Focused registered node for ``bcftools_mpileup``."""

from bionodulo.nodes.builtin.bcftools_family.calling_adapter import BCFtoolsMpileupNode as _NodeContract


class BCFtoolsMpileupNode(_NodeContract):
    NODE_ID = 'bcftools_mpileup'

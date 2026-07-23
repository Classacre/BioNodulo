"""Focused registered node for ``bcftools_norm``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsNormNode as _NodeContract


class BCFtoolsNormNode(_NodeContract):
    NODE_ID = 'bcftools_norm'

"""Focused registered node for ``bcftools_merge``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsMergeNode as _NodeContract


class BCFtoolsMergeNode(_NodeContract):
    NODE_ID = 'bcftools_merge'

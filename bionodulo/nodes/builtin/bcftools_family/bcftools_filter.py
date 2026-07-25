"""Focused registered node for ``bcftools_filter``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsFilterNode as _NodeContract


class BCFtoolsFilterNode(_NodeContract):
    NODE_ID = 'bcftools_filter'

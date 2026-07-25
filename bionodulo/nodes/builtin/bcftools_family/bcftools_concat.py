"""Focused registered node for ``bcftools_concat``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsConcatNode as _NodeContract


class BCFtoolsConcatNode(_NodeContract):
    NODE_ID = 'bcftools_concat'

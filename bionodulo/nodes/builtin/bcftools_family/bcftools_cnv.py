"""Focused registered node for ``bcftools_cnv``."""

from bionodulo.nodes.builtin.bcftools_family.analysis_adapter import BCFtoolsCNVNode as _NodeContract


class BCFtoolsCNVNode(_NodeContract):
    NODE_ID = 'bcftools_cnv'

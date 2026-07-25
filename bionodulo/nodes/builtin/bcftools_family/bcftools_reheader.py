"""Focused registered node for ``bcftools_reheader``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsReheaderNode as _NodeContract


class BCFtoolsReheaderNode(_NodeContract):
    NODE_ID = 'bcftools_reheader'

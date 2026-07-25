"""Focused registered node for ``bcftools_isec``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsIsecNode as _NodeContract


class BCFtoolsIsecNode(_NodeContract):
    NODE_ID = 'bcftools_isec'

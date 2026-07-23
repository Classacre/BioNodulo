"""Focused registered node for ``bcftools_view``."""

from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import BCFtoolsViewNode as _NodeContract


class BCFtoolsViewNode(_NodeContract):
    NODE_ID = 'bcftools_view'

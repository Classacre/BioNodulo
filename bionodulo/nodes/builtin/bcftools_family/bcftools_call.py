"""Focused registered node for ``bcftools_call``."""

from bionodulo.nodes.builtin.bcftools_family.calling_adapter import BCFtoolsCallNode as _NodeContract


class BCFtoolsCallNode(_NodeContract):
    NODE_ID = 'bcftools_call'

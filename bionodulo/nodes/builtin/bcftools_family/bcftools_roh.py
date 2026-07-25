"""Focused registered node for ``bcftools_roh``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsROHNode as _NodeContract


class BCFtoolsROHNode(_NodeContract):
    NODE_ID = 'bcftools_roh'

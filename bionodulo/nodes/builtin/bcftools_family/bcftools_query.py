"""Focused registered node for ``bcftools_query``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsQueryNode as _NodeContract


class BCFtoolsQueryNode(_NodeContract):
    NODE_ID = 'bcftools_query'

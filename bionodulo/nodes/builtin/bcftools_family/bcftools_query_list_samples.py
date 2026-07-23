"""Focused registered node for ``bcftools_query_list_samples``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsQueryListSamplesNode as _NodeContract


class BCFtoolsQueryListSamplesNode(_NodeContract):
    NODE_ID = 'bcftools_query_list_samples'

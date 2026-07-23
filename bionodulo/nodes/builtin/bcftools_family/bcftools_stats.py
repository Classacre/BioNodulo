"""Focused registered node for ``bcftools_stats``."""

from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import BCFtoolsStatsNode as _NodeContract


class BCFtoolsStatsNode(_NodeContract):
    NODE_ID = 'bcftools_stats'

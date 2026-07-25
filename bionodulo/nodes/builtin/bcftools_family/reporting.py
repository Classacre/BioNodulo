"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.reporting_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.reporting_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_consensus import BCFtoolsConsensusNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_gtcheck import BCFtoolsGTcheckNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_query import BCFtoolsQueryNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_query_list_samples import BCFtoolsQueryListSamplesNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_roh import BCFtoolsROHNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_stats import BCFtoolsStatsNode

__all__ = ['BCFtoolsConsensusNode', 'BCFtoolsGTcheckNode', 'BCFtoolsQueryNode', 'BCFtoolsQueryListSamplesNode', 'BCFtoolsROHNode', 'BCFtoolsStatsNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

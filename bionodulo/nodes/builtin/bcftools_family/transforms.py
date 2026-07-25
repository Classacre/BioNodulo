"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.transforms_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.transforms_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_concat import BCFtoolsConcatNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_filter import BCFtoolsFilterNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_isec import BCFtoolsIsecNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_merge import BCFtoolsMergeNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_norm import BCFtoolsNormNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_reheader import BCFtoolsReheaderNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_view import BCFtoolsViewNode

__all__ = ['BCFtoolsConcatNode', 'BCFtoolsFilterNode', 'BCFtoolsIsecNode', 'BCFtoolsMergeNode', 'BCFtoolsNormNode', 'BCFtoolsReheaderNode', 'BCFtoolsViewNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.calling_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.calling_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_call import BCFtoolsCallNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_mpileup import BCFtoolsMpileupNode

__all__ = ['BCFtoolsCallNode', 'BCFtoolsMpileupNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

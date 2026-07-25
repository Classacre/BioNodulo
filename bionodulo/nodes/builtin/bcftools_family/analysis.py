"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.analysis_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.analysis_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_cnv import BCFtoolsCNVNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_csq import BCFtoolsCSQNode

__all__ = ['BCFtoolsCNVNode', 'BCFtoolsCSQNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

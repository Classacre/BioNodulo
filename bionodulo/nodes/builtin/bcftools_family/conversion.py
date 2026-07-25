"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.conversion_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.conversion_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_convert_from_vcf import BCFtoolsConvertFromVcfNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_convert_to_vcf import BCFtoolsConvertToVcfNode

__all__ = ['BCFtoolsConvertFromVcfNode', 'BCFtoolsConvertToVcfNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

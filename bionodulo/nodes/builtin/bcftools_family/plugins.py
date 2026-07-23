"""Compatibility exports for focused one-node modules."""

import bionodulo.nodes.builtin.bcftools_family.plugins_adapter as _adapter
from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import *  # noqa: F403

from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_color_chrs import BCFtoolsPluginColorChrsNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_counts import BCFtoolsPluginCountsNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_dosage import BCFtoolsPluginDosageNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_fill_an_ac import BCFtoolsPluginFillAnAcNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_fill_tags import BCFtoolsPluginFillTagsNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_fixploidy import BCFtoolsPluginFixploidyNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_frameshifts import BCFtoolsPluginFrameshiftsNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_impute_info import BCFtoolsPluginImputeInfoNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_mendelian import BCFtoolsPluginMendelianNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_missing2ref import BCFtoolsPluginMissing2refNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_setgt import BCFtoolsPluginSetgtNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_split_vep import BCFtoolsPluginSplitVepNode
from bionodulo.nodes.builtin.bcftools_family.bcftools_plugin_tag2tag import BCFtoolsPluginTag2tagNode

__all__ = ['BCFtoolsPluginColorChrsNode', 'BCFtoolsPluginCountsNode', 'BCFtoolsPluginDosageNode', 'BCFtoolsPluginFillAnAcNode', 'BCFtoolsPluginFillTagsNode', 'BCFtoolsPluginFixploidyNode', 'BCFtoolsPluginFrameshiftsNode', 'BCFtoolsPluginImputeInfoNode', 'BCFtoolsPluginMendelianNode', 'BCFtoolsPluginMissing2refNode', 'BCFtoolsPluginSetgtNode', 'BCFtoolsPluginSplitVepNode', 'BCFtoolsPluginTag2tagNode']


def __getattr__(name: str):
    return getattr(_adapter, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_adapter)))

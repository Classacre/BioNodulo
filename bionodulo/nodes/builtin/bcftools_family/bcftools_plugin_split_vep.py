"""Focused registered node for ``bcftools_plugin_split_vep``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginSplitVepNode as _NodeContract


class BCFtoolsPluginSplitVepNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_split_vep'

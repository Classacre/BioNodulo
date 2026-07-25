"""Focused registered node for ``bcftools_plugin_counts``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginCountsNode as _NodeContract


class BCFtoolsPluginCountsNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_counts'

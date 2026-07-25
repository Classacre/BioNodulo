"""Focused registered node for ``bcftools_plugin_fill_tags``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginFillTagsNode as _NodeContract


class BCFtoolsPluginFillTagsNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_fill_tags'

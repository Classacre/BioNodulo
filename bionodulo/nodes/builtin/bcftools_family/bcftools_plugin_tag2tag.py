"""Focused registered node for ``bcftools_plugin_tag2tag``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginTag2tagNode as _NodeContract


class BCFtoolsPluginTag2tagNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_tag2tag'

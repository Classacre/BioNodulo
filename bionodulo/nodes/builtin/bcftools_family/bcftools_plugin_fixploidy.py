"""Focused registered node for ``bcftools_plugin_fixploidy``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginFixploidyNode as _NodeContract


class BCFtoolsPluginFixploidyNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_fixploidy'

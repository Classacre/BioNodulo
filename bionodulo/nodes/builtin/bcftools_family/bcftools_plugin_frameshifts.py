"""Focused registered node for ``bcftools_plugin_frameshifts``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginFrameshiftsNode as _NodeContract


class BCFtoolsPluginFrameshiftsNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_frameshifts'

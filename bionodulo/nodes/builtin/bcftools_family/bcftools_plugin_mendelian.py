"""Focused registered node for ``bcftools_plugin_mendelian``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginMendelianNode as _NodeContract


class BCFtoolsPluginMendelianNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_mendelian'

"""Focused registered node for ``bcftools_plugin_dosage``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginDosageNode as _NodeContract


class BCFtoolsPluginDosageNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_dosage'

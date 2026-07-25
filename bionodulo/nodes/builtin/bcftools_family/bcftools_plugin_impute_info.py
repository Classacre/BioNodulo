"""Focused registered node for ``bcftools_plugin_impute_info``."""

from bionodulo.nodes.builtin.bcftools_family.plugins_adapter import BCFtoolsPluginImputeInfoNode as _NodeContract


class BCFtoolsPluginImputeInfoNode(_NodeContract):
    NODE_ID = 'bcftools_plugin_impute_info'

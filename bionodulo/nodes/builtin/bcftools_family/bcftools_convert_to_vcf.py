"""Focused registered node for ``bcftools_convert_to_vcf``."""

from bionodulo.nodes.builtin.bcftools_family.conversion_adapter import BCFtoolsConvertToVcfNode as _NodeContract


class BCFtoolsConvertToVcfNode(_NodeContract):
    NODE_ID = 'bcftools_convert_to_vcf'

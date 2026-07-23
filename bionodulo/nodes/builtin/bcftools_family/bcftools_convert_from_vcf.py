"""Focused registered node for ``bcftools_convert_from_vcf``."""

from bionodulo.nodes.builtin.bcftools_family.conversion_adapter import BCFtoolsConvertFromVcfNode as _NodeContract


class BCFtoolsConvertFromVcfNode(_NodeContract):
    NODE_ID = 'bcftools_convert_from_vcf'

"""Stable owner for ``vcf_comparison``."""

from .legacy import _VCFComparisonContract


class VCFComparisonNode(_VCFComparisonContract):
    NODE_ID = "vcf_comparison"

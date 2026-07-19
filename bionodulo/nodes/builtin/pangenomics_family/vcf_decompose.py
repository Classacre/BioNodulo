"""Stable owner for ``vcf_decompose``."""

from .legacy import _VCFDecomposeContract


class VCFDecomposeNode(_VCFDecomposeContract):
    NODE_ID = "vcf_decompose"

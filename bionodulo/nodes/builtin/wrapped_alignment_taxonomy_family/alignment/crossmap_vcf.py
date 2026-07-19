"""Stable owner for ``crossmap_vcf``."""

from .adapter import _CrossMapVcfContract


class CrossMapVcfNode(_CrossMapVcfContract):
    NODE_ID = "crossmap_vcf"
    UPSTREAM_SYMBOL = "CrossMapVcfNode"

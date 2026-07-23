"""Focused owner for ``crossmap_vcf``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _CrossMapVcfContract


class CrossMapVcfNode(_CrossMapVcfContract):
    NODE_ID = "crossmap_vcf"
    UPSTREAM_SYMBOL = "CrossMapVcfNode"

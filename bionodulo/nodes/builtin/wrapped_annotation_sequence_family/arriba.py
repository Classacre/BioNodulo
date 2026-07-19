"""Stable owner for ``arriba``."""

from .legacy import _ArribaContract


class ArribaNode(_ArribaContract):
    NODE_ID = "arriba"
    OUTPUT_NAME_BY_BASENAME = {
        "fusions.tsv": "fusions_tsv",
        "fusions.discarded.tsv": "discarded_fusions_tsv",
        "fusions.vcf": "fusions_vcf",
        "fusion_bams": "fusion_bams",
        "fusions.pdf": "fusions_pdf",
    }

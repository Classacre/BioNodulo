"""Focused owner for ``arriba``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _ArribaContract


class ArribaNode(_ArribaContract):
    NODE_ID = "arriba"
    OUTPUT_NAME_BY_BASENAME = {
        "fusions.tsv": "fusions_tsv",
        "fusions.discarded.tsv": "discarded_fusions_tsv",
        "fusions.vcf": "fusions_vcf",
        "fusion_bams": "fusion_bams",
        "fusions.pdf": "fusions_pdf",
    }

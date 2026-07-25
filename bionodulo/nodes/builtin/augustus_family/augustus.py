"""Focused owner for ``augustus``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _AugustusContract


class AugustusNode(_AugustusContract):
    NODE_ID = "augustus"
    OUTPUT_NAME_BY_BASENAME = {
        "augustus.gtf": "output",
        "augustus.gff3": "output",
        "protein.fasta": "protein_output",
        "codingseq.fasta": "codingseq_output",
    }

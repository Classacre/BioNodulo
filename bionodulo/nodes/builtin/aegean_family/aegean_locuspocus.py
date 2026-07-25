"""Focused owner for ``aegean_locuspocus``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _AegeanLocusPocusContract


class AegeanLocusPocusNode(_AegeanLocusPocusContract):
    NODE_ID = "aegean_locuspocus"
    OUTPUT_NAME_BY_BASENAME = {
        "loci.gff3": "output",
        "ilens.tsv": "output_ilens",
        "genemap.tsv": "output_genemap",
        "transmap.tsv": "output_transmap",
    }

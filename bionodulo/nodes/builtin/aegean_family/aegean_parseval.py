"""Focused owner for ``aegean_parseval``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _AegeanParsevalContract


class AegeanParsevalNode(_AegeanParsevalContract):
    NODE_ID = "aegean_parseval"
    OUTPUT_NAME_BY_BASENAME = {
        "parseval.txt": "output_txt",
        "parseval.html": "output_html",
    }

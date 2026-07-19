"""GFF/GTF workflow input node."""

from .adapter import _InputGFFContract


class InputGFFNode(_InputGFFContract):
    """Import a GFF3 or GTF annotation file."""

    NODE_ID = "input_gff"

"""FASTA workflow input node."""

from .adapter import _InputFASTAContract


class InputFASTANode(_InputFASTAContract):
    """Import a FASTA reference or sequence file."""

    NODE_ID = "input_fasta"

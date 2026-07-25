"""FASTQ workflow input node."""

from .adapter import _InputFASTQContract


class InputFASTQNode(_InputFASTQContract):
    """Import one single-end or two paired-end FASTQ files."""

    NODE_ID = "input_fastq"

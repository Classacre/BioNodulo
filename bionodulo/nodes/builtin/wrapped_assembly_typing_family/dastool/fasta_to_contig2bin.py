"""Stable owner for ``fasta_to_contig2bin``."""

from .adapter import _FastaToContig2BinContract


class FastaToContig2BinNode(_FastaToContig2BinContract):
    NODE_ID = "fasta_to_contig2bin"
    UPSTREAM_SYMBOL = "FastaToContig2BinNode"

"""Stable owner for ``seqkit_grep``."""

from .legacy import _SeqKitGrepContract


class SeqKitGrepNode(_SeqKitGrepContract):
    NODE_ID = "seqkit_grep"
    OUTPUT_NAME_BY_BASENAME = {
        "grep.fasta": "fasta_output",
        "grep.fasta.gz": "fasta_output",
        "grep.fastq": "fastq_output",
        "grep.fastq.gz": "fastq_output",
        "count.txt": "count",
    }

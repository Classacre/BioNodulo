"""Compatibility node ID for the focused SRA Toolkit download contract."""

from .sra_download import SRADownloadNode


class SRAFetchNode(SRADownloadNode):
    """Expose the same pinned SRA Toolkit contract under the historical ID."""

    NODE_ID = "sra_fetch"
    DISPLAY_NAME = "SRA Fetch"
    DESCRIPTION = "Fetch SRA runs and convert them to FASTQ or FASTA with SRA Toolkit 3.4.1."
    SEARCH_ALIASES = [
        "sra fetch",
        "sra",
        "sequence read archive",
        "download",
        "fastq",
        "fasta",
        "prefetch",
        "fasterq-dump",
    ]

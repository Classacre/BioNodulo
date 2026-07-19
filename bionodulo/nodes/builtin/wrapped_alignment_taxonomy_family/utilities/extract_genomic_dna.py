"""Stable owner for ``Extract genomic DNA 1``."""

from .adapter import _ExtractGenomicDnaContract


class ExtractGenomicDnaNode(_ExtractGenomicDnaContract):
    NODE_ID = "Extract genomic DNA 1"
    UPSTREAM_SYMBOL = "ExtractGenomicDnaNode"

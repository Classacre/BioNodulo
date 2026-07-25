"""Focused owner for ``Extract genomic DNA 1``."""

from bionodulo.nodes.builtin._alignment_taxonomy_utilities_adapter import _ExtractGenomicDnaContract


class ExtractGenomicDnaNode(_ExtractGenomicDnaContract):
    NODE_ID = "Extract genomic DNA 1"
    UPSTREAM_SYMBOL = "ExtractGenomicDnaNode"

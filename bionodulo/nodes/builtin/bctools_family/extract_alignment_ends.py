"""Focused owner for ``bctools_extract_alignment_ends``."""

from .adapter import _BctoolsExtractAlignmentEndsContract


class BctoolsExtractAlignmentEndsNode(_BctoolsExtractAlignmentEndsContract):
    NODE_ID = "bctools_extract_alignment_ends"
    UPSTREAM_SYMBOL = "BctoolsExtractAlignmentEndsNode"

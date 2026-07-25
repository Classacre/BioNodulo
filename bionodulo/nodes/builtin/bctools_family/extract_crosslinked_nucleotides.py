"""Focused owner for ``bctools_extract_crosslinked_nucleotides``."""

from .adapter import _BctoolsExtractCrosslinkedNucleotidesContract


class BctoolsExtractCrosslinkedNucleotidesNode(_BctoolsExtractCrosslinkedNucleotidesContract):
    NODE_ID = "bctools_extract_crosslinked_nucleotides"
    UPSTREAM_SYMBOL = "BctoolsExtractCrosslinkedNucleotidesNode"

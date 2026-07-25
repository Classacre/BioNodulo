"""Focused owner for ``bctools_merge_pcr_duplicates``."""

from .adapter import _BctoolsMergePcrDuplicatesContract


class BctoolsMergePcrDuplicatesNode(_BctoolsMergePcrDuplicatesContract):
    NODE_ID = "bctools_merge_pcr_duplicates"
    UPSTREAM_SYMBOL = "BctoolsMergePcrDuplicatesNode"

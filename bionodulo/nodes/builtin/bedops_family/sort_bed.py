"""Canonical BEDOPS sort-bed node."""

from .adapter import BEDOPSSortBedBase, COMMON_SEARCH_ALIASES


class BEDOPSSortBedNode(BEDOPSSortBedBase):
    NODE_ID = "bedops_sort_bed"
    DISPLAY_NAME = "BEDOPS Sort BED"
    SEARCH_ALIASES = COMMON_SEARCH_ALIASES

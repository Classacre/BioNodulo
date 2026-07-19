"""Galaxy stable-ID alias for BEDOPS sort-bed."""

from .adapter import COMMON_SEARCH_ALIASES
from .sort_bed import BEDOPSSortBedNode


class BEDOPSSortBedGalaxyNode(BEDOPSSortBedNode):
    NODE_ID = "bedops-sort-bed"
    DISPLAY_NAME = "BEDOPS sort-bed"
    SEARCH_ALIASES = [*COMMON_SEARCH_ALIASES, "bedops-sort-bed"]

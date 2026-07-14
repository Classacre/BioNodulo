"""bedops — wrapped_bedtools node(s). One tool per file (extracted from wrapped_bedtools.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BEDOPSSortBedGalaxyNode(BEDOPSSortBedNode):
    """Galaxy wrapper-ID compatible alias for BEDOPS sort-bed."""
    NODE_ID = 'bedops-sort-bed'
    DISPLAY_NAME = 'BEDOPS sort-bed'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'bedops-sort-bed', 'bedops', 'sort-bed', 'BEDOPS sort-bed', 'sort BED', 'unique BED', 'duplicate BED']

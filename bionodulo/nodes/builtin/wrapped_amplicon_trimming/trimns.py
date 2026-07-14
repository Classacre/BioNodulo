"""trimns — wrapped_amplicon_trimming node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class TrimNGalaxyNode(TrimNNode):
    """Galaxy wrapper-ID compatible alias for TrimN."""
    NODE_ID = 'trimns'
    DISPLAY_NAME = 'TrimN (Galaxy)'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'trimns', 'TrimN', 'trimns_vgp', 'trim_Ns_DNAnexus.py', 'remove fake cut sites', 'bionano scaffolds', 'VGP']

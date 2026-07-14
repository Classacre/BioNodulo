"""abyss — wrapped_variant_assembly node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ABySSPEGalaxyNode(ABySSPENode):
    """Galaxy wrapper ID for the ABySS paired-end pipeline."""
    NODE_ID = 'abyss-pe'
    DISPLAY_NAME = 'ABySS (Galaxy)'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ABySS', 'abyss-pe', 'de novo assembler', 'short read assembly', 'paired-end assembly', 'genome assembler']

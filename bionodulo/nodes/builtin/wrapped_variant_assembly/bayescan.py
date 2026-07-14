"""bayescan — wrapped_variant_assembly node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BayeScanGalaxyNode(BayeScanNode):
    """Galaxy wrapper ID for BayeScan."""
    NODE_ID = 'BayeScan'
    DISPLAY_NAME = 'BayeScan (Galaxy)'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BayeScan', 'bayescan2', 'natural selection', 'population genetics', 'FST', 'genome scan', 'dominant markers', 'codominant markers']

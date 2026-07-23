"""Focused owner for the historical ``BayeScan`` alias."""

from .adapter import BayeScanGalaxyNode as _NodeContract
from .bayescan import BayeScanNode


class BayeScanGalaxyNode(_NodeContract, BayeScanNode):
    NODE_ID = "BayeScan"
    UPSTREAM_SYMBOL = "BayeScanGalaxyNode"

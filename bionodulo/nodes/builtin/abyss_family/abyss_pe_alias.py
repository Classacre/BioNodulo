"""Focused owner for the historical ``abyss-pe`` alias."""

from .abyss_pe import ABySSPENode
from .adapter import ABySSPEGalaxyNode as _NodeContract


class ABySSPEGalaxyNode(_NodeContract, ABySSPENode):
    NODE_ID = "abyss-pe"
    UPSTREAM_SYMBOL = "ABySSPEGalaxyNode"

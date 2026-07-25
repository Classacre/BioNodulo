"""Focused registered node for ``trimns``."""

from .trimn import TrimNNode
from .trimn_adapter import TrimNGalaxyNode as _NodeContract


class TrimNGalaxyNode(_NodeContract, TrimNNode):
    NODE_ID = "trimns"

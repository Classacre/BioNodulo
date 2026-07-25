"""Focused registered node for ``baredsc_combine_2d``."""

from .baredsc_2d import Baredsc2DNode
from .adapter import BaredscCombine2DNode as _NodeContract


class BaredscCombine2DNode(_NodeContract, Baredsc2DNode):
    NODE_ID = "baredsc_combine_2d"

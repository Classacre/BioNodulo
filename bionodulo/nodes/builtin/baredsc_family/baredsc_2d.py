"""Focused registered node for ``baredsc_2d``."""

from .baredsc_1d import Baredsc1DNode
from .adapter import Baredsc2DNode as _NodeContract


class Baredsc2DNode(_NodeContract, Baredsc1DNode):
    NODE_ID = "baredsc_2d"

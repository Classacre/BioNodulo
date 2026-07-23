"""Focused registered node for ``baredsc_combine_1d``."""

from .baredsc_1d import Baredsc1DNode
from .adapter import BaredscCombine1DNode as _NodeContract


class BaredscCombine1DNode(_NodeContract, Baredsc1DNode):
    NODE_ID = "baredsc_combine_1d"

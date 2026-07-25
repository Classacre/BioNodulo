"""Focused owner for ``amas_remove``."""

from .adapter import AMASRemoveNode as _NodeContract
from .amas_concat import AMASConcatNode


class AMASRemoveNode(_NodeContract, AMASConcatNode):
    NODE_ID = "amas_remove"

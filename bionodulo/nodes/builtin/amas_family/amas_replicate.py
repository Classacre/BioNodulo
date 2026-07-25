"""Focused owner for ``amas_replicate``."""

from .adapter import AMASReplicateNode as _NodeContract
from .amas_concat import AMASConcatNode


class AMASReplicateNode(_NodeContract, AMASConcatNode):
    NODE_ID = "amas_replicate"

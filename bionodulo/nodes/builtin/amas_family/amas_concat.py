"""Focused owner for ``amas_concat``."""

from .adapter import AMASConcatNode as _NodeContract
from .amas_summary import AMASSummaryNode


class AMASConcatNode(_NodeContract, AMASSummaryNode):
    NODE_ID = "amas_concat"

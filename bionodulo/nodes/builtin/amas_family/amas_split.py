"""Focused owner for ``amas_split``."""

from .adapter import AMASSplitNode as _NodeContract
from .amas_summary import AMASSummaryNode


class AMASSplitNode(_NodeContract, AMASSummaryNode):
    NODE_ID = "amas_split"

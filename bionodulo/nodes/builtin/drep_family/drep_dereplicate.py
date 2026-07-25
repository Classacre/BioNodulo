"""Focused owner for ``drep_dereplicate``."""

from .adapter import DrepDereplicateNode as _NodeContract
from .drep_compare import DrepCompareNode


class DrepDereplicateNode(_NodeContract, DrepCompareNode):
    NODE_ID = "drep_dereplicate"
    UPSTREAM_SYMBOL = "DrepDereplicateNode"

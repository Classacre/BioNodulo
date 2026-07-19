"""Stable owner for ``checkm_tree_qa``."""

from .adapter import _CheckMTreeQAContract


class CheckMTreeQANode(_CheckMTreeQAContract):
    NODE_ID = "checkm_tree_qa"
    UPSTREAM_SYMBOL = "CheckMTreeQANode"

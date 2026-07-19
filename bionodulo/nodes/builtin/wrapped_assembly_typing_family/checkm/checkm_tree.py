"""Stable owner for ``checkm_tree``."""

from .adapter import _CheckMTreeContract


class CheckMTreeNode(_CheckMTreeContract):
    NODE_ID = "checkm_tree"
    UPSTREAM_SYMBOL = "CheckMTreeNode"

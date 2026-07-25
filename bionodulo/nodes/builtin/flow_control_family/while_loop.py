"""Stable owner for the ``while_loop`` node."""

from .adapter import _WhileLoopContract


class WhileLoopNode(_WhileLoopContract):
    """Track bounded conditional loop state between executor passes."""

    NODE_ID = "while_loop"
    UPSTREAM_SYMBOL = "WhileLoopNode"

"""Stable owner for the ``if_condition`` node."""

from .adapter import _IfConditionContract


class IfConditionNode(_IfConditionContract):
    """Route one value through a validated conditional branch."""

    NODE_ID = "if_condition"
    UPSTREAM_SYMBOL = "IfConditionNode"

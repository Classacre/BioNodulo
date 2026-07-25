"""Stable owner for the ``switch`` node."""

from .adapter import _SwitchContract


class SwitchNode(_SwitchContract):
    """Select one or more dynamically declared output branches."""

    NODE_ID = "switch"
    UPSTREAM_SYMBOL = "SwitchNode"

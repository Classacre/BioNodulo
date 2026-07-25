"""Stable owner for the ``sleep`` node."""

from .adapter import _SleepContract


class SleepNode(_SleepContract):
    """Await one non-negative duration and pass through a value."""

    NODE_ID = "sleep"
    UPSTREAM_SYMBOL = "SleepNode"

"""Stable owner for the ``delay_wait`` node."""

from .adapter import _DelayWaitContract


class DelayWaitNode(_DelayWaitContract):
    """Await a duration, timestamp, file predicate, process, or URL."""

    NODE_ID = "delay_wait"
    UPSTREAM_SYMBOL = "DelayWaitNode"

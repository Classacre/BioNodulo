"""Stable owner for the ``wait_for`` node."""

from .adapter import _WaitForContract


class WaitForNode(_WaitForContract):
    """Await a file predicate or elapsed-time condition."""

    NODE_ID = "wait_for"
    UPSTREAM_SYMBOL = "WaitForNode"

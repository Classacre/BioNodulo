"""Stable owner for the ``try_catch`` node."""

from .adapter import _TryCatchContract


class TryCatchNode(_TryCatchContract):
    """Route try, retry, and catch phases without blocking the event loop."""

    NODE_ID = "try_catch"
    UPSTREAM_SYMBOL = "TryCatchNode"

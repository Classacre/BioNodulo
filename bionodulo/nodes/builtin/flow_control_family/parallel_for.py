"""Stable owner for the ``parallel_for`` node."""

from .adapter import _ParallelForContract


class ParallelForNode(_ParallelForContract):
    """Describe bounded scatter and deterministic gather behavior."""

    NODE_ID = "parallel_for"
    UPSTREAM_SYMBOL = "ParallelForNode"

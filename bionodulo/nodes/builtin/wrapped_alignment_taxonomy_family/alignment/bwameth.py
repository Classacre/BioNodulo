"""Stable owner for ``bwameth``."""

from .adapter import _BwaMethContract


class BwaMethNode(_BwaMethContract):
    NODE_ID = "bwameth"
    UPSTREAM_SYMBOL = "BwaMethNode"

"""Focused registered owner for ``heinz``."""

from .adapter import HeinzNode as _NodeContract


class HeinzNode(_NodeContract):
    NODE_ID = "heinz"

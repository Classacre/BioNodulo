"""Focused registered owner for ``heinz_bum``."""

from .adapter import HeinzBumNode as _NodeContract


class HeinzBumNode(_NodeContract):
    NODE_ID = "heinz_bum"

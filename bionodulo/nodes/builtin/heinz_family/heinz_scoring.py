"""Focused registered owner for ``heinz_scoring``."""

from .adapter import HeinzScoringNode as _NodeContract


class HeinzScoringNode(_NodeContract):
    NODE_ID = "heinz_scoring"

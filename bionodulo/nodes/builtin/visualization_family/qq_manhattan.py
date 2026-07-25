"""Focused registered owner for ``qq_manhattan``."""

from .qq_manhattan_adapter import QQManhattanNode as _NodeContract


class QQManhattanNode(_NodeContract):
    NODE_ID = "qq_manhattan"

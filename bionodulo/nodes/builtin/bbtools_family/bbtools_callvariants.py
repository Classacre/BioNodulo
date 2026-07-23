"""Focused owner for ``bbtools_callvariants``."""

from .adapter import BBToolsCallVariantsNode as _NodeContract


class BBToolsCallVariantsNode(_NodeContract):
    NODE_ID = "bbtools_callvariants"

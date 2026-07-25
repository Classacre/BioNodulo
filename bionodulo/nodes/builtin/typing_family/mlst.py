"""Focused registered node for ``mlst``."""

from .adapter import MLSTNode as _NodeContract


class MLSTNode(_NodeContract):
    NODE_ID = "mlst"

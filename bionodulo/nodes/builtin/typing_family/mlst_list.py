"""Focused registered node for ``mlst_list``."""

from .adapter import MLSTListNode as _NodeContract


class MLSTListNode(_NodeContract):
    NODE_ID = "mlst_list"

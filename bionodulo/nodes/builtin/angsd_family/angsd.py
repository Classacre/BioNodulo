"""Focused registered node for ``angsd``."""

from .adapter import ANGSDNode as _NodeContract


class ANGSDNode(_NodeContract):
    NODE_ID = "angsd"

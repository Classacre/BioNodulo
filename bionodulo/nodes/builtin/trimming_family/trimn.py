"""Focused registered node for ``trimn``."""

from .trimn_adapter import TrimNNode as _NodeContract


class TrimNNode(_NodeContract):
    NODE_ID = "trimn"

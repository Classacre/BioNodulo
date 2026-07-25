"""Focused registered node for ``ampvis2_core``."""

from .diversity_adapter import Ampvis2CoreNode as _NodeContract


class Ampvis2CoreNode(_NodeContract):
    NODE_ID = "ampvis2_core"

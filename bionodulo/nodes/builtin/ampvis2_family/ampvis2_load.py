"""Focused registered node for ``ampvis2_load``."""

from .io_adapter import Ampvis2LoadNode as _NodeContract


class Ampvis2LoadNode(_NodeContract):
    NODE_ID = "ampvis2_load"

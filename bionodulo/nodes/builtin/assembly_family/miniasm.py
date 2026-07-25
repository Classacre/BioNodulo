"""Focused registered node for ``miniasm``."""

from .wrapped_assembly_adapter import MiniasmNode as _NodeContract


class MiniasmNode(_NodeContract):
    NODE_ID = "miniasm"

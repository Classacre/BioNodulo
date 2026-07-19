"""Stable owner for ``shovill``."""

from .assembly_adapter import _ShovillContract


class ShovillNode(_ShovillContract):
    NODE_ID = "shovill"
    UPSTREAM_SYMBOL = "ShovillNode"

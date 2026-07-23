"""Focused owner for ``shovill``."""

from bionodulo.nodes.builtin._bacterial_assembly_adapter import _ShovillContract


class ShovillNode(_ShovillContract):
    NODE_ID = "shovill"
    UPSTREAM_SYMBOL = "ShovillNode"

"""Focused owner for ``snippy_core``."""

from bionodulo.nodes.builtin._bacterial_assembly_adapter import _SnippyCoreContract


class SnippyCoreNode(_SnippyCoreContract):
    NODE_ID = "snippy_core"
    UPSTREAM_SYMBOL = "SnippyCoreNode"

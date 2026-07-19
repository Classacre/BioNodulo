"""Stable owner for ``snippy_core``."""

from .assembly_adapter import _SnippyCoreContract


class SnippyCoreNode(_SnippyCoreContract):
    NODE_ID = "snippy_core"
    UPSTREAM_SYMBOL = "SnippyCoreNode"

"""Focused owner for ``snippy``."""

from bionodulo.nodes.builtin._bacterial_assembly_adapter import _SnippyContract


class SnippyNode(_SnippyContract):
    NODE_ID = "snippy"
    UPSTREAM_SYMBOL = "SnippyNode"

"""Stable owner for ``snippy``."""

from .assembly_adapter import _SnippyContract


class SnippyNode(_SnippyContract):
    NODE_ID = "snippy"
    UPSTREAM_SYMBOL = "SnippyNode"

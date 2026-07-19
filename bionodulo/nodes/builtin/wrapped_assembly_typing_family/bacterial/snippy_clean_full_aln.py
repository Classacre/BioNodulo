"""Stable owner for ``snippy_clean_full_aln``."""

from .assembly_adapter import _SnippyCleanFullAlnContract


class SnippyCleanFullAlnNode(_SnippyCleanFullAlnContract):
    NODE_ID = "snippy_clean_full_aln"
    UPSTREAM_SYMBOL = "SnippyCleanFullAlnNode"

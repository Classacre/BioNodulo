"""Focused owner for ``snippy_clean_full_aln``."""

from bionodulo.nodes.builtin._bacterial_assembly_adapter import _SnippyCleanFullAlnContract


class SnippyCleanFullAlnNode(_SnippyCleanFullAlnContract):
    NODE_ID = "snippy_clean_full_aln"
    UPSTREAM_SYMBOL = "SnippyCleanFullAlnNode"

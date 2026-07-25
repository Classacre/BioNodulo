"""Focused owner for ``bwameth``."""

from bionodulo.nodes.builtin._alignment_taxonomy_alignment_adapter import _BwaMethContract


class BwaMethNode(_BwaMethContract):
    NODE_ID = "bwameth"
    UPSTREAM_SYMBOL = "BwaMethNode"

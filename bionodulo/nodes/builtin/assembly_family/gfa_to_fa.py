"""Focused owner for ``gfa_to_fa``."""

from .gfa_adapter import _GfaToFaContract


class GfaToFaNode(_GfaToFaContract):
    NODE_ID = "gfa_to_fa"
    UPSTREAM_SYMBOL = "GfaToFaNode"

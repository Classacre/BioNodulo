"""Focused owner for ``raven``."""

from bionodulo.nodes.builtin._bacterial_assembly_adapter import _RavenContract


class RavenNode(_RavenContract):
    NODE_ID = "raven"
    UPSTREAM_SYMBOL = "RavenNode"

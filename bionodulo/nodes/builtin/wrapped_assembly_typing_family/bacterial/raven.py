"""Stable owner for ``raven``."""

from .assembly_adapter import _RavenContract


class RavenNode(_RavenContract):
    NODE_ID = "raven"
    UPSTREAM_SYMBOL = "RavenNode"

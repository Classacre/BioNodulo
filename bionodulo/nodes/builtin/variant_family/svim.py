"""Stable owner for ``svim``."""

from .legacy import _SVIMContract


class SVIMNode(_SVIMContract):
    NODE_ID = "svim"

"""Stable owner for ``kaiju2krona``."""

from .adapter import _Kaiju2KronaContract


class Kaiju2KronaNode(_Kaiju2KronaContract):
    NODE_ID = "kaiju2krona"
    UPSTREAM_SYMBOL = "Kaiju2KronaNode"

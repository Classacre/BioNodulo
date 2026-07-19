"""Stable owner for ``som.py``."""

from .adapter import _HappySompyContract


class HappySompyNode(_HappySompyContract):
    NODE_ID = "som.py"
    UPSTREAM_SYMBOL = "HappySompyNode"

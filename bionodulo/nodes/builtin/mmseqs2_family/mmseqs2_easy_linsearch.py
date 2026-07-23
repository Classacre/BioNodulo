"""Stable owner for ``mmseqs2_easy_linsearch``."""

from .adapter import _MMseqs2EasyLinsearchContract


class MMseqs2EasyLinsearchNode(_MMseqs2EasyLinsearchContract):
    NODE_ID = "mmseqs2_easy_linsearch"
    UPSTREAM_SYMBOL = "MMseqs2EasyLinsearchNode"

"""Stable owner for ``mmseqs2_easy_search``."""

from .adapter import _MMseqs2EasySearchContract


class MMseqs2EasySearchNode(_MMseqs2EasySearchContract):
    NODE_ID = "mmseqs2_easy_search"
    UPSTREAM_SYMBOL = "MMseqs2EasySearchNode"

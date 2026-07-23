"""Stable owner for ``mmseqs2_easy_rbh``."""

from .adapter import _MMseqs2EasyRBHContract


class MMseqs2EasyRBHNode(_MMseqs2EasyRBHContract):
    NODE_ID = "mmseqs2_easy_rbh"
    UPSTREAM_SYMBOL = "MMseqs2EasyRBHNode"

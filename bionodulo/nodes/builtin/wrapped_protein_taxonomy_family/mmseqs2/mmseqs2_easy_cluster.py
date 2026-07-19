"""Stable owner for ``mmseqs2_easy_cluster``."""

from .adapter import _MMseqs2EasyClusterContract


class MMseqs2EasyClusterNode(_MMseqs2EasyClusterContract):
    NODE_ID = "mmseqs2_easy_cluster"
    UPSTREAM_SYMBOL = "MMseqs2EasyClusterNode"

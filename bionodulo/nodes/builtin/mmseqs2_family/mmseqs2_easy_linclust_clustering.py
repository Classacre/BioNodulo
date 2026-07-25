"""Stable owner for ``mmseqs2_easy_linclust_clustering``."""

from .adapter import _MMseqs2EasyLinclustContract


class MMseqs2EasyLinclustNode(_MMseqs2EasyLinclustContract):
    NODE_ID = "mmseqs2_easy_linclust_clustering"
    UPSTREAM_SYMBOL = "MMseqs2EasyLinclustNode"

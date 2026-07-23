"""Stable owner for ``mmseqs2_easy_taxonomy``."""

from .adapter import _MMseqs2EasyTaxonomyContract


class MMseqs2EasyTaxonomyNode(_MMseqs2EasyTaxonomyContract):
    NODE_ID = "mmseqs2_easy_taxonomy"
    UPSTREAM_SYMBOL = "MMseqs2EasyTaxonomyNode"

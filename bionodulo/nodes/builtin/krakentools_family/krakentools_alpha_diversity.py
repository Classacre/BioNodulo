"""Stable owner for ``krakentools_alpha_diversity``."""

from .adapter import _KrakentoolsAlphaDiversityContract


class KrakentoolsAlphaDiversityNode(_KrakentoolsAlphaDiversityContract):
    NODE_ID = "krakentools_alpha_diversity"
    UPSTREAM_SYMBOL = "KrakentoolsAlphaDiversityNode"

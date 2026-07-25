"""Stable owner for ``krakentools_beta_diversity``."""

from .adapter import _KrakentoolsBetaDiversityContract


class KrakentoolsBetaDiversityNode(_KrakentoolsBetaDiversityContract):
    NODE_ID = "krakentools_beta_diversity"
    UPSTREAM_SYMBOL = "KrakentoolsBetaDiversityNode"

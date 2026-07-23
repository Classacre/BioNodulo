"""Stable owner for ``krakentools_combine_kreports``."""

from .adapter import _KrakentoolsCombineKreportsContract


class KrakentoolsCombineKreportsNode(_KrakentoolsCombineKreportsContract):
    NODE_ID = "krakentools_combine_kreports"
    UPSTREAM_SYMBOL = "KrakentoolsCombineKreportsNode"

"""Stable owner for ``krakentools_kreport2mpa``."""

from .adapter import _KrakentoolsKreport2MpaContract


class KrakentoolsKreport2MpaNode(_KrakentoolsKreport2MpaContract):
    NODE_ID = "krakentools_kreport2mpa"
    UPSTREAM_SYMBOL = "KrakentoolsKreport2MpaNode"

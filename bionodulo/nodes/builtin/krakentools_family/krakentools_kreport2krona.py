"""Stable owner for ``krakentools_kreport2krona``."""

from .adapter import _KrakentoolsKreport2KronaContract


class KrakentoolsKreport2KronaNode(_KrakentoolsKreport2KronaContract):
    NODE_ID = "krakentools_kreport2krona"
    UPSTREAM_SYMBOL = "KrakentoolsKreport2KronaNode"

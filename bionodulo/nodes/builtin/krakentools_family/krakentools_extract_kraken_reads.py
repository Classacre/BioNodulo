"""Stable owner for ``krakentools_extract_kraken_reads``."""

from .adapter import _KrakentoolsExtractKrakenReadsContract


class KrakentoolsExtractKrakenReadsNode(_KrakentoolsExtractKrakenReadsContract):
    NODE_ID = "krakentools_extract_kraken_reads"
    UPSTREAM_SYMBOL = "KrakentoolsExtractKrakenReadsNode"

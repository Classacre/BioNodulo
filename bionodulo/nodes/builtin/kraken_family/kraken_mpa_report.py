"""Stable owner for ``kraken_mpa_report``."""

from .adapter import _KrakenMpaReportContract


class KrakenMpaReportNode(_KrakenMpaReportContract):
    NODE_ID = "kraken_mpa_report"
    UPSTREAM_SYMBOL = "KrakenMpaReportNode"

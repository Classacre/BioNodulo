"""Stable owner for ``kraken_report``."""

from .adapter import _KrakenReportContract


class KrakenReportNode(_KrakenReportContract):
    NODE_ID = "kraken_report"
    UPSTREAM_SYMBOL = "KrakenReportNode"

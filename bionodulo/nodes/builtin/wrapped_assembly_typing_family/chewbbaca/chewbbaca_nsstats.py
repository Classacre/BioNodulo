"""Stable owner for ``chewbbaca_nsstats``."""

from .adapter import _ChewBBACANSStatsContract


class ChewBBACANSStatsNode(_ChewBBACANSStatsContract):
    NODE_ID = "chewbbaca_nsstats"
    UPSTREAM_SYMBOL = "ChewBBACANSStatsNode"

"""Stable owner for ``sv_stats``."""

from .legacy import _SVStatsContract


class SVStatsNode(_SVStatsContract):
    NODE_ID = "sv_stats"

"""Stable owner for ``pangenome_stats``."""

from .legacy import _PangenomeStatsContract


class PangenomeStatsNode(_PangenomeStatsContract):
    NODE_ID = "pangenome_stats"

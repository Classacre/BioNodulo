"""Stable owner for ``seqkit_stats``."""

from .legacy import _SeqKitStatsContract


class SeqKitStatsNode(_SeqKitStatsContract):
    NODE_ID = "seqkit_stats"

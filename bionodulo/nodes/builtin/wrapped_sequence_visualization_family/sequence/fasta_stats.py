"""Stable owner for ``fasta-stats``."""

from ..adapter import _FastaStatsContract


class FastaStatsNode(_FastaStatsContract):
    NODE_ID = "fasta-stats"

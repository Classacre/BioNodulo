"""Stable owner for ``fasta-stats``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _FastaStatsContract


class FastaStatsNode(_FastaStatsContract):
    NODE_ID = "fasta-stats"

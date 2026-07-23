"""Focused owner for ``seqkit_stats``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _SeqKitStatsContract


class SeqKitStatsNode(_SeqKitStatsContract):
    NODE_ID = "seqkit_stats"

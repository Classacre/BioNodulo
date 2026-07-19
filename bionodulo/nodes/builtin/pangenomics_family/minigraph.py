"""Stable owner for ``minigraph``."""

from .legacy import _MinigraphContract


class MinigraphNode(_MinigraphContract):
    NODE_ID = "minigraph"
    OUTPUT_NAME_BY_BASENAME = {
        "output_gfa.gfa": "output_gfa",
        "alignment_gaf.gaf": "alignment_gaf",
    }

"""Compatibility alias for the focused Squidpy QC owner."""

from .squidpy_qc import SquidpyQCNode


class SquidpyNode(SquidpyQCNode):
    """Preserve the original ``squidpy`` ID with ID-specific output paths."""

    NODE_ID = "squidpy"
    DISPLAY_NAME = "Squidpy"
    DESCRIPTION = "Run Visium QC, clustering, and spatial-neighborhood enrichment with Squidpy."

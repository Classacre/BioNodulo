"""Compatibility facade for focused R bioinformatics node modules."""

from bionodulo.nodes.builtin.r_family import (
    BiostringsStatsNode,
    DESeq2AliasNode,
    DESeq2Node,
    PheatmapNode,
)

__all__ = ["BiostringsStatsNode", "DESeq2AliasNode", "DESeq2Node", "PheatmapNode"]

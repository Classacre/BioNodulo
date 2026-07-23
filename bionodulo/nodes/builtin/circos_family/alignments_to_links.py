"""Stable owner for ``circos_aln_to_links``."""

from bionodulo.nodes.builtin.sequence_visualization_family.adapter import _CircosAlignmentsToLinksContract


class CircosAlignmentsToLinksNode(_CircosAlignmentsToLinksContract):
    NODE_ID = "circos_aln_to_links"

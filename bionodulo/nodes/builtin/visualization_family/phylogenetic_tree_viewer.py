"""Stable owner for the ``phylogenetic_tree_viewer`` compatibility ID."""

from .phylo_tree_viewer import PhylogeneticTreeViewerNode


class PhylogeneticTreeViewerCompatibilityNode(PhylogeneticTreeViewerNode):
    """Preserve the original tree-viewer ID with the identical proven contract."""

    NODE_ID = "phylogenetic_tree_viewer"
    UPSTREAM_SYMBOL = "PhylogeneticTreeViewerCompatibilityNode"

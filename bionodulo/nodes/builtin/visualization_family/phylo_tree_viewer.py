"""Stable owner for the ``phylo_tree_viewer`` node."""

from .adapter import _PhylogeneticTreeViewerContract


class PhylogeneticTreeViewerNode(_PhylogeneticTreeViewerContract):
    """Parse and render Newick trees with optional bootstrap labels."""

    NODE_ID = "phylo_tree_viewer"
    UPSTREAM_SYMBOL = "PhylogeneticTreeViewerNode"

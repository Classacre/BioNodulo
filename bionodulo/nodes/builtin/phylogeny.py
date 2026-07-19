"""Compatibility facade for focused phylogeny node owners."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.phylogeny_family import (
    ASTRALNode,
    ClustalONode,
    EBIClustalOmegaNode,
    FastTreeNode,
    IQTREENode,
    MAFFTNode,
    ModelTestNGNode,
    MUSCLENode,
    PhylogeneticTreeBuilderNode,
    PhyloTNode,
    RAxMLNGNode,
    RAxMLNode,
    TrimAlNode,
)

__all__ = [name for name in globals() if name.endswith("Node")]

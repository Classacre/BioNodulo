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

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "ASTRALNode",
    "ClustalONode",
    "EBIClustalOmegaNode",
    "FastTreeNode",
    "IQTREENode",
    "MAFFTNode",
    "MUSCLENode",
    "ModelTestNGNode",
    "PhyloTNode",
    "PhylogeneticTreeBuilderNode",
    "RAxMLNGNode",
    "RAxMLNode",
    "TrimAlNode",
]

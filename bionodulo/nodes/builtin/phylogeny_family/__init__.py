"""Focused source-pinned phylogeny node owners."""

from .astral import ASTRALNode
from .clustalo import ClustalONode
from .ebi_clustal_omega import EBIClustalOmegaNode
from .fasttree import FastTreeNode
from .iqtree import IQTREENode
from .mafft import MAFFTNode
from .modeltest_ng import ModelTestNGNode
from .muscle import MUSCLENode
from .phylogenetic_tree_builder import PhylogeneticTreeBuilderNode
from .phylot import PhyloTNode
from .raxml import RAxMLNode
from .raxml_ng import RAxMLNGNode
from .trimal import TrimAlNode

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

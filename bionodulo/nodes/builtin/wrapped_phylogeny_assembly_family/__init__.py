"""Focused, evidence-pinned phylogeny and assembly wrapper nodes."""

from .assembly_stats import AssemblyStatsNode
from .amas import AMASConcatNode, AMASRemoveNode, AMASReplicateNode, AMASSplitNode, AMASSummaryNode
from .classic_phylogeny import ClustalWNode, PhyMLNode, QuicktreeNode, RapidNJNode
from .read_merging import FLASHNode, PEARNode
from .microbial_gene_tools import AbriTAMRNode, EukRepNode, FragGeneScanNode, GAMMANode, GAMMASNode, NonpareilNode, ProdigalNode, RedNode
from .bbtools import BBToolsBBDukNode, BBToolsBBMapNode, BBToolsBBMergeNode, BBToolsBBNormNode, BBToolsCallVariantsNode, BBToolsTadpoleNode
from .assembly_qc import GenomeScopeNode, MiniaNode, PlasClassNode, PlasFlowNode
from .art import ART454Node, ARTIlluminaNode, ARTSOLiDNode
from .amplican import AmpliCanNode
from .allegro import AllegroNode
from .alphagenome import AlphaGenomeIntervalPredictorNode, AlphaGenomeISMScannerNode, AlphaGenomeSequencePredictorNode, AlphaGenomeVariantEffectNode, AlphaGenomeVariantScorerNode

__all__ = [
    "AssemblyStatsNode",
    "AMASSummaryNode",
    "AMASConcatNode",
    "AMASSplitNode",
    "AMASRemoveNode",
    "AMASReplicateNode",
    "ClustalWNode",
    "QuicktreeNode",
    "RapidNJNode",
    "PhyMLNode",
    "FLASHNode",
    "PEARNode",
    "FragGeneScanNode",
    "ProdigalNode",
    "EukRepNode",
    "GAMMANode",
    "GAMMASNode",
    "RedNode",
    "AbriTAMRNode",
    "NonpareilNode",
    "BBToolsBBDukNode",
    "BBToolsBBMergeNode",
    "BBToolsBBNormNode",
    "BBToolsTadpoleNode",
    "BBToolsCallVariantsNode",
    "BBToolsBBMapNode",
    "PlasClassNode",
    "PlasFlowNode",
    "MiniaNode",
    "GenomeScopeNode",
    "ARTIlluminaNode",
    "ART454Node",
    "ARTSOLiDNode",
    "AmpliCanNode",
    "AllegroNode",
    "AlphaGenomeIntervalPredictorNode",
    "AlphaGenomeISMScannerNode",
    "AlphaGenomeSequencePredictorNode",
    "AlphaGenomeVariantEffectNode",
    "AlphaGenomeVariantScorerNode"
]

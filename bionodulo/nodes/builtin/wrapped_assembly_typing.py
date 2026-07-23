"""Compatibility facade for focused assembly and typing wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.abricate_family import (
    ABRicateListNode,
    ABRicateNode,
    ABRicateSummaryNode,
)
from bionodulo.nodes.builtin.bandage_family import BandageImageNode, BandageInfoNode
from bionodulo.nodes.builtin.checkm_family import (
    CheckM2Node,
    CheckMAnalyzeNode,
    CheckMLineageSetNode,
    CheckMLineageWFNode,
    CheckMPlotNode,
    CheckMQANode,
    CheckMTaxonSetNode,
    CheckMTaxonomyWFNode,
    CheckMTetraNode,
    CheckMTreeNode,
    CheckMTreeQANode,
)
from bionodulo.nodes.builtin.chewbbaca_family import (
    ChewBBACAAlleleCallEvaluatorNode,
    ChewBBACAAlleleCallNode,
    ChewBBACACreateSchemaNode,
    ChewBBACADownloadSchemaNode,
    ChewBBACAExtractCgMLSTNode,
    ChewBBACAJoinProfilesNode,
    ChewBBACANSStatsNode,
    ChewBBACAPrepExternalSchemaNode,
)
from bionodulo.nodes.builtin.chira_family import (
    CheRRIEvalNode,
    CheRRITrainNode,
    ChiraCollapseNode,
    ChiraExtractNode,
    ChiraMapNode,
    ChiraMergeNode,
    ChiraQuantifyNode,
)
from bionodulo.nodes.builtin.assembly_family.gfa_to_fa import GfaToFaNode
from bionodulo.nodes.builtin.assembly_family.raven import RavenNode
from bionodulo.nodes.builtin.assembly_family.shovill import ShovillNode
from bionodulo.nodes.builtin.annotation_family.plasmidfinder import PlasmidFinderNode
from bionodulo.nodes.builtin.annotation_family.staramr_search import StaramrSearchNode
from bionodulo.nodes.builtin.metagenomics_family.das_tool import DASToolNode
from bionodulo.nodes.builtin.metagenomics_family.fasta_to_contig2bin import FastaToContig2BinNode
from bionodulo.nodes.builtin.snippy_family import SnippyCleanFullAlnNode, SnippyCoreNode, SnippyNode
from bionodulo.nodes.builtin.typing_family.kleborate import KleborateNode

__all__ = [name for name in globals() if name.endswith("Node")]

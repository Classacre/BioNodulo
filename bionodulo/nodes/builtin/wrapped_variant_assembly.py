"""Compatibility facade for focused variant and assembly wrapper nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.abyss_family import ABySSPEGalaxyNode, ABySSPENode
from bionodulo.nodes.builtin.alignment_family.exonerate import ExonerateNode
from bionodulo.nodes.builtin.annotation_family.evidencemodeler import EvidenceModelerNode
from bionodulo.nodes.builtin.annotation_family.fargene import FargeneNode
from bionodulo.nodes.builtin.assembly_family.bellerophon import BellerophonNode
from bionodulo.nodes.builtin.assembly_family.biscot import BiSCoTNode
from bionodulo.nodes.builtin.assembly_family.compleasm import CompleasmNode
from bionodulo.nodes.builtin.bayescan_family import BayeScanGalaxyNode, BayeScanNode
from bionodulo.nodes.builtin.bioext_family import BioExtBam2MsaNode, BioExtBealignNode
from bionodulo.nodes.builtin.cami_amber_family import (
    CamiAmberAddNode,
    CamiAmberConvertNode,
    CamiAmberNode,
)
from bionodulo.nodes.builtin.comebin_family import COMEBinBamNode, COMEBinNode
from bionodulo.nodes.builtin.comparative_genomics_family.chromeister import ChromeisterNode
from bionodulo.nodes.builtin.drep_family import DrepCompareNode, DrepDereplicateNode
from bionodulo.nodes.builtin.fastspar_family import (
    FastSparNode,
    FastSparPvaluesNode,
    FastSparReduceNode,
)
from bionodulo.nodes.builtin.freyja_family import (
    FreyjaAggregatePlotNode,
    FreyjaBootNode,
    FreyjaDemixNode,
    FreyjaVariantsNode,
)
from bionodulo.nodes.builtin.genomics_family.bigwig_outlier import BigWigOutlierBedNode
from bionodulo.nodes.builtin.graphlan_family import (
    Export2GraphlanNode,
    GraphlanAnnotateNode,
    GraphlanNode,
)
from bionodulo.nodes.builtin.image_analysis_family.biapy import BiaPyNode
from bionodulo.nodes.builtin.ivar_family import (
    IVarConsensusNode,
    IVarFilterVariantsNode,
    IVarRemoveReadsNode,
    IVarTrimNode,
    IVarVariantsNode,
)
from bionodulo.nodes.builtin.lofreq_family import (
    LoFreqAlnQualNode,
    LoFreqCallNode,
    LoFreqFilterNode,
    LoFreqIndelQualNode,
    LoFreqViterbiNode,
)
from bionodulo.nodes.builtin.metabat2_family import (
    MetaBAT2JgiSummarizeBamContigDepthsNode,
    MetaBAT2Node,
)
from bionodulo.nodes.builtin.metagenomics_family.binette import BinetteNode
from bionodulo.nodes.builtin.metagenomics_family.binning_refiner import BinningRefinerNode
from bionodulo.nodes.builtin.metagenomics_family.biobox_add_taxid import BioboxAddTaxidNode
from bionodulo.nodes.builtin.preseq_family import PreseqCCurveNode, PreseqLCExtrapNode
from bionodulo.nodes.builtin.rna_seq_family.eastr import EASTRNode
from bionodulo.nodes.builtin.secondary_metabolism_family.bigscape import BiGSCAPENode
from bionodulo.nodes.builtin.sequence_family.ampligone import AmpliGoneNode
from bionodulo.nodes.builtin.taxonomy_family.gtdbtk import GTDBTkClassifyWFNode
from bionodulo.nodes.builtin.variant_family.beagle import BeagleNode
from bionodulo.nodes.builtin.variant_family.breseq import BreseqNode
from bionodulo.nodes.builtin.visualization_family.bellavista import BellavistaPrepareNode

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "ABySSPEGalaxyNode",
    "ABySSPENode",
    "AmpliGoneNode",
    "BayeScanGalaxyNode",
    "BayeScanNode",
    "BeagleNode",
    "BellavistaPrepareNode",
    "BellerophonNode",
    "BiGSCAPENode",
    "BiSCoTNode",
    "BiaPyNode",
    "BigWigOutlierBedNode",
    "BinetteNode",
    "BinningRefinerNode",
    "BioExtBam2MsaNode",
    "BioExtBealignNode",
    "BioboxAddTaxidNode",
    "BreseqNode",
    "COMEBinBamNode",
    "COMEBinNode",
    "CamiAmberAddNode",
    "CamiAmberConvertNode",
    "CamiAmberNode",
    "ChromeisterNode",
    "CompleasmNode",
    "DrepCompareNode",
    "DrepDereplicateNode",
    "EASTRNode",
    "EvidenceModelerNode",
    "ExonerateNode",
    "Export2GraphlanNode",
    "FargeneNode",
    "FastSparNode",
    "FastSparPvaluesNode",
    "FastSparReduceNode",
    "FreyjaAggregatePlotNode",
    "FreyjaBootNode",
    "FreyjaDemixNode",
    "FreyjaVariantsNode",
    "GTDBTkClassifyWFNode",
    "GraphlanAnnotateNode",
    "GraphlanNode",
    "IVarConsensusNode",
    "IVarFilterVariantsNode",
    "IVarRemoveReadsNode",
    "IVarTrimNode",
    "IVarVariantsNode",
    "LoFreqAlnQualNode",
    "LoFreqCallNode",
    "LoFreqFilterNode",
    "LoFreqIndelQualNode",
    "LoFreqViterbiNode",
    "MetaBAT2JgiSummarizeBamContigDepthsNode",
    "MetaBAT2Node",
    "PreseqCCurveNode",
    "PreseqLCExtrapNode",
]

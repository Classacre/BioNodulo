"""Compatibility facade for focused epigenomics nodes."""

from bionodulo.nodes.builtin.bismark_family.align import BismarkAlignNode
from bionodulo.nodes.builtin.bismark_family.genome_preparation import BismarkGenomePreparationNode
from bionodulo.nodes.builtin.bismark_family.methylation_extractor import (
    BismarkMethylationExtractorNode,
    BismarkMethylationNode,
)
from bionodulo.nodes.builtin.deeptools_family.bam_coverage import DeepToolsBamCoverageNode
from bionodulo.nodes.builtin.deeptools_family.compute_matrix import DeepToolsComputeMatrixNode
from bionodulo.nodes.builtin.deeptools_family.plot_heatmap import DeepToolsPlotHeatmapNode
from bionodulo.nodes.builtin.deeptools_family.plot_profile import DeepToolsPlotProfileNode
from bionodulo.nodes.builtin.epigenomics_family import (
    CoolerNode,
    CooltoolsCompartmentsNode,
    CooltoolsInsulationNode,
    DSSDMRNode,
    DSS_DMR_SCRIPT,
    HICProNode,
    JuicerNode,
    MethylDackelNode,
    ModkitDMRNode,
)

__all__ = [
    "BismarkAlignNode",
    "BismarkGenomePreparationNode",
    "BismarkMethylationExtractorNode",
    "BismarkMethylationNode",
    "CoolerNode",
    "CooltoolsCompartmentsNode",
    "CooltoolsInsulationNode",
    "DSSDMRNode",
    "DSS_DMR_SCRIPT",
    "DeepToolsBamCoverageNode",
    "DeepToolsComputeMatrixNode",
    "DeepToolsPlotHeatmapNode",
    "DeepToolsPlotProfileNode",
    "HICProNode",
    "JuicerNode",
    "MethylDackelNode",
    "ModkitDMRNode",
]

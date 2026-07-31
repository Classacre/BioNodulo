"""Compatibility facade for Beacon2, HEINZ, GFF, BREW3R, QQ, and UCSC nodes."""
# ruff: noqa: F401

from bionodulo.nodes.builtin.annotation_family import Brew3rRNode, GffCompareNode, GffReadNode
from bionodulo.nodes.builtin.beacon2_family import (
    Beacon2Csv2XlsxNode,
    Beacon2ImportNode,
    Beacon2Pxf2BffNode,
    Beacon2Vcf2BffNode,
)
from bionodulo.nodes.builtin.heinz_family import (
    HeinzBumNode,
    HeinzNode,
    HeinzScoringNode,
    HeinzVisualizationNode,
)
from bionodulo.nodes.builtin.ucsc_family import (
    FaSplitNode,
    FaToVcfNode,
    GtfToBed12Node,
    MafToAxtNode,
    UcscAxtChainNode,
    UcscAxtToMafNode,
    UcscChainAntiRepeatNode,
    UcscChainNetNode,
    UcscChainPreNetNode,
    UcscChainSortNode,
    UcscChainSwapNode,
    UcscMafAddIRowsNode,
    UcscMafCoverageNode,
    UcscMafFetchNode,
    UcscMafFilterNode,
    UcscMafFragNode,
    UcscMafFragsNode,
    UcscMafGeneNode,
    UcscNetChainSubsetNode,
    UcscNetFilterNode,
    UcscNetSyntenicNode,
    UcscNetToAxtNode,
    UcscTwoBitToFaNode,
    UcscWigToBigWigNode,
)
from bionodulo.nodes.builtin.visualization_family import QQManhattanNode

# Explicit, not `[name for name in globals() ...]`: mypy evaluates __all__
# statically, so a comprehension over globals() made `import *` export
# nothing as far as the type checker was concerned, and every name in every
# consuming module became an undefined-name error. That pattern accounted
# for roughly 8000 of the repository's 8535 mypy errors. The contents below
# are exactly what the comprehension produced at import time.
__all__ = [
    "Beacon2Csv2XlsxNode",
    "Beacon2ImportNode",
    "Beacon2Pxf2BffNode",
    "Beacon2Vcf2BffNode",
    "Brew3rRNode",
    "FaSplitNode",
    "FaToVcfNode",
    "GffCompareNode",
    "GffReadNode",
    "GtfToBed12Node",
    "HeinzBumNode",
    "HeinzNode",
    "HeinzScoringNode",
    "HeinzVisualizationNode",
    "MafToAxtNode",
    "QQManhattanNode",
    "UcscAxtChainNode",
    "UcscAxtToMafNode",
    "UcscChainAntiRepeatNode",
    "UcscChainNetNode",
    "UcscChainPreNetNode",
    "UcscChainSortNode",
    "UcscChainSwapNode",
    "UcscMafAddIRowsNode",
    "UcscMafCoverageNode",
    "UcscMafFetchNode",
    "UcscMafFilterNode",
    "UcscMafFragNode",
    "UcscMafFragsNode",
    "UcscMafGeneNode",
    "UcscNetChainSubsetNode",
    "UcscNetFilterNode",
    "UcscNetSyntenicNode",
    "UcscNetToAxtNode",
    "UcscTwoBitToFaNode",
    "UcscWigToBigWigNode",
]
